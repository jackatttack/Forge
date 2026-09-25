# -*- coding: utf-8 -*-
"""
RUN Forge op.

Execute one project-relative Python script in-process and capture output.
"""

import contextlib
import io
import os
import sys
import traceback
import types

from forge.core.file_safety import safe_target


SPEC = {
    'name': 'RUN',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'ARGS',
        'CONFIRM',
        'OUTPUT',
        'STOP_ON_FAIL',
    ]),
    'required_directives': set(),
}


# ---- Output shaping settings ------------------------------------------------
#
# OUTPUT lets a bundle keep repeated, passing runs short in the packet.
# Editable: how many lines "tail" keeps by default, and the most it accepts.
DEFAULT_TAIL_LINES = 8
MAX_TAIL_LINES = 200

OUTPUT_USAGE = (
    'OUTPUT must be full, tail, tail N (1-%d) or summary' % MAX_TAIL_LINES
)


HELP = {
    'summary': 'Execute a project-relative Python file in-process and capture its output.',
    'brief': (
        'OUTPUT: tail|summary shortens a passing run (failures always show '
        'everything) · STOP_ON_FAIL: yes makes a non-zero exit gate the '
        'rest of the bundle · ARGS sets argv.'
    ),
    'minimal_example': [
        'RUN smoke.py',
        '',
        'RUN tools/check.py',
        'ARGS: --quick "two words"',
    ],
    'directives': {
        'ARGS': (
            'Optional command-line arguments parsed with shell-like quoting.'
        ),
        'CONFIRM': (
            'Explicitly permits execution when the script path is protected by the core guard.'
        ),
        'STOP_ON_FAIL': (
            'With yes, a non-zero exit stops every later mutation and RUN, '
            'so a test RUN can gate the rest of the bundle.'
        ),
        'OUTPUT': (
            'How much output a successful run shows: full (default), '
            'tail (last %d lines of each stream), tail N, or summary '
            '(last line of each stream). A failed run always shows full '
            'output, and result data always keeps everything.'
            % DEFAULT_TAIL_LINES
        ),
    },
    'internal_directives': [],
    'common_failures': [
        'The target is missing, outside the project root, or not a .py file.',
        'The script raises an exception.',
        'The script exits with a non-zero SystemExit code.',
    ],
    'safe_usage': [
        'READ unfamiliar scripts before executing them.',
        'Do not run Forge entrypoints from inside an active Forge run.',
        'Keep script output bounded; OUTPUT only shortens successful runs.',
        'Use OUTPUT: tail or summary on test RUNs that are rerun often.',
        'Remember that in-process execution is not a security boundary.',
    ],
    'related_ops': [
        'READ inspects a script before execution.',
        'MAP locates likely project entrypoints.',
        'BRANCH checkpoints files before a script that may mutate them.',
    ],
}


HINTS = {
    '_max_hints': 1,

    'target': {
        'message': 'RUN needs a Python file path.',
        'why': 'Forge needs to know which project-relative script to execute.',
        'example': [
            'RUN smoke.py',
        ],
        'next': [
            'Use MAP to locate the script.',
            'Use READ before running unfamiliar code.',
        ],
    },

    'not found': {
        'message': 'RUN could not find the target script.',
        'why': 'The path must exist inside project_root.',
        'next': [
            'Check the path with MAP.',
            'Use WRITE if the script has not been created yet.',
        ],
    },

    'exited': {
        'message': 'The script exited with a non-zero code.',
        'why': 'RUN treats non-zero SystemExit as a failed run.',
        'next': [
            'Read captured stdout/stderr.',
            'Patch the failing code and rerun.',
        ],
    },

    'output must': {
        'message': 'OUTPUT has an unsupported value.',
        'why': 'OUTPUT chooses how much of a successful run the packet shows.',
        'example': [
            'RUN tests/run_all.py',
            'OUTPUT: tail 12',
        ],
        'next': [
            'Use full, tail, tail N or summary.',
        ],
    },

    'exception': {
        'message': 'The script raised an exception.',
        'why': 'RUN captures traceback text so the failure can be inspected and patched.',
        'next': [
            'Use READ around the traceback line.',
            'Patch with REPLACE or INSERT.',
        ],
    },
}


def _parse_output_mode(raw):
    """
    Read an OUTPUT directive value as (mode, tail_lines, error).

        full     every line (also the default when OUTPUT is absent)
        tail     the last DEFAULT_TAIL_LINES lines of each stream
        tail N   the last N lines of each stream
        summary  the last line of each stream

    tail_lines is None for full. error is '' when the value is valid.
    """
    words = str(raw or '').strip().lower().split()

    if not words or words == ['full']:
        return 'full', None, ''

    if words == ['summary']:
        return 'summary', 1, ''

    if words[0] == 'tail':
        if len(words) == 1:
            return 'tail', DEFAULT_TAIL_LINES, ''
        if len(words) == 2 and words[1].isdigit():
            count = int(words[1])
            if 1 <= count <= MAX_TAIL_LINES:
                return 'tail', count, ''

    return None, None, '%s; got %r' % (OUTPUT_USAGE, str(raw).strip())


def _last_lines(text, count):
    """Return (the last count lines of text, how many earlier lines were dropped)."""
    lines = text.splitlines()
    hidden = max(0, len(lines) - count)
    return '\n'.join(lines[hidden:]), hidden


def validate(parsed_op):
    target = (
        parsed_op.get('target')
        or ''
    ).strip()

    if not target:
        return [
            'RUN requires a target path'
        ]

    directives = parsed_op.get('directives') or {}
    _, _, output_error = _parse_output_mode(directives.get('OUTPUT'))
    if output_error:
        return [output_error]

    return []


def _split_args(raw):
    raw = str(
        raw
        or ''
    ).strip()

    if not raw:
        return []

    try:
        import shlex
        return shlex.split(raw)
    except Exception:
        return raw.split()


def _script_exit(code=None):
    """Give scripts standard exit semantics even when the host replaces sys.exit."""
    raise SystemExit(code)

def _exit_code_from_system_exit(exc):
    code = exc.code

    if code is None:
        return 0

    if isinstance(
        code,
        int,
    ):
        return int(code)

    return 1


def _format_preview(
    path,
    exit_code,
    stdout_text,
    stderr_text,
    tail_lines=None,
):
    """
    Build the packet preview for one RUN.

    tail_lines None shows every captured line. A number keeps only the
    last lines of each stream and says how many were hidden. execute()
    passes a number only for successful runs, so a failure always shows
    everything.
    """
    lines = ['RUN %s [exit %s]' % (path, exit_code)]
    hidden_total = 0

    for stream_name, text in (('stdout', stdout_text), ('stderr', stderr_text)):
        if not text:
            continue

        shown = text.rstrip()
        heading = '--- %s ---' % stream_name

        if tail_lines is not None:
            shown, hidden = _last_lines(shown, tail_lines)
            if hidden:
                heading = '--- %s (%s earlier lines hidden) ---' % (
                    stream_name,
                    hidden,
                )
                hidden_total += hidden

        lines.append(heading)
        lines.append(shown)

    if not stdout_text and not stderr_text:
        lines.append('(no output)')

    if hidden_total:
        lines.append(
            '(OUTPUT hid %s lines of a passing run; OUTPUT: full shows them)'
            % hidden_total
        )

    return '\n'.join(lines).rstrip()


def execute(ctx, parsed_op, result):
    target = (
        parsed_op.get('target')
        or ''
    ).strip()

    directives = (
        parsed_op.get('directives')
        or {}
    )

    root, abs_path, err = safe_target(
        ctx,
        target,
    )

    if err:
        result['status'] = (
            'FAILED_INVALID_PATH'
        )
        result['message'] = err
        return

    if not os.path.isfile(
        abs_path
    ):
        result['status'] = (
            'FAILED_NOT_FOUND'
        )
        result['message'] = (
            'File not found: '
            + target
        )
        return

    if not target.endswith(
        '.py'
    ):
        result['status'] = (
            'FAILED_INVALID_PATH'
        )
        result['message'] = (
            'RUN target must be a .py file'
        )
        return

    try:
        with open(
            abs_path,
            'r',
            encoding='utf-8',
        ) as f:
            source = f.read()

    except Exception as e:
        result['status'] = (
            'FAILED_IO'
        )
        result['message'] = (
            '%s: %s'
            % (
                type(e).__name__,
                e,
            )
        )
        return

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exit_code = 0

    old_argv = sys.argv[:]
    old_cwd = os.getcwd()
    old_path = sys.path[:]
    old_exit = sys.exit
    missing_main = object()
    old_main = sys.modules.get('__main__', missing_main)

    script_dir = os.path.dirname(
        abs_path
    )

    argv = [
        abs_path
    ] + _split_args(
        directives.get(
            'ARGS'
        )
    )

    # Discovery and imports of __main__ must see the executing script.
    script_module = types.ModuleType('__main__')
    ns = script_module.__dict__
    ns.update({
        '__file__': abs_path,
        '__package__': None,
        '__spec__': None,
        '__builtins__': __builtins__,
    })

    try:
        sys.modules['__main__'] = script_module
        # Some hosts turn sys.exit into KeyboardInterrupt. Preserve the
        # script's requested exit code by providing standard semantics here.
        sys.exit = _script_exit
        sys.argv = argv
        os.chdir(root)

        for path in (
            script_dir,
            root,
        ):
            if (
                path
                and path not in sys.path
            ):
                sys.path.insert(
                    0,
                    path,
                )

        with contextlib.redirect_stdout(
            stdout_buffer
        ):
            with contextlib.redirect_stderr(
                stderr_buffer
            ):
                compiled = compile(
                    source,
                    abs_path,
                    'exec',
                )
                exec(
                    compiled,
                    ns,
                    ns,
                )

    except SystemExit as e:
        exit_code = _exit_code_from_system_exit(e)
        if e.code is not None and not isinstance(e.code, int):
            print(str(e.code), file=stderr_buffer)

    except KeyboardInterrupt:
        exit_code = 130
        traceback.print_exc(file=stderr_buffer)

    except BaseException:
        # This is the script execution boundary. Even GeneratorExit or a
        # custom BaseException must become an observable script failure.
        exit_code = 1
        traceback.print_exc(file=stderr_buffer)

    finally:
        sys.exit = old_exit
        if old_main is missing_main:
            sys.modules.pop('__main__', None)
        else:
            sys.modules['__main__'] = old_main
        sys.argv = old_argv
        sys.path[:] = old_path
        os.chdir(old_cwd)

    stdout_text = (
        stdout_buffer.getvalue()
    )

    stderr_text = (
        stderr_buffer.getvalue()
    )

    # OUTPUT only shortens what a successful run shows in the packet.
    # Failures keep every line, and result data always keeps everything.
    output_mode, tail_lines, _ = _parse_output_mode(
        directives.get('OUTPUT')
    )
    shown_tail_lines = tail_lines if exit_code == 0 else None

    result['preview'] = _format_preview(
        target,
        exit_code,
        stdout_text,
        stderr_text,
        tail_lines=shown_tail_lines,
    )

    result['data'] = {
        'path': target,
        'exit_code': exit_code,
        'stdout': stdout_text,
        'stderr': stderr_text,
        'output': output_mode,
    }

    if exit_code == 0:
        result['status'] = 'APPLIED'
        result['message'] = 'exit 0'
    else:
        result['status'] = (
            'FAILED_RUNTIME'
        )
        result['message'] = (
            'Script exited with code %s'
            % exit_code
        )