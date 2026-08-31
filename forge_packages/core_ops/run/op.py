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

from forge_core.file_safety import safe_target


SPEC = {
    'name': 'RUN',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'ARGS',
        'CONFIRM',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Execute a Python file under the project root and capture stdout/stderr.',
    'minimal_example': [
        'RUN smoke.py',
        '',
        'RUN tools/check.py',
        'ARGS: --quick',
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

    'exception': {
        'message': 'The script raised an exception.',
        'why': 'RUN captures traceback text so the failure can be inspected and patched.',
        'next': [
            'Use READ around the traceback line.',
            'Patch with REPLACE or INSERT.',
        ],
    },
}


def validate(parsed_op):
    target = (
        parsed_op.get('target')
        or ''
    ).strip()

    if not target:
        return [
            'RUN requires a target path'
        ]

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


def _exit_code_from_system_exit(exc):
    code = exc.code

    if code is None:
        return 0

    if isinstance(
        code,
        int,
    ):
        return code

    return 1


def _format_preview(
    path,
    exit_code,
    stdout_text,
    stderr_text,
):
    lines = [
        'RUN %s [exit %s]'
        % (
            path,
            exit_code,
        )
    ]

    if stdout_text:
        lines.append(
            '--- stdout ---'
        )
        lines.append(
            stdout_text.rstrip()
        )

    if stderr_text:
        lines.append(
            '--- stderr ---'
        )
        lines.append(
            stderr_text.rstrip()
        )

    if not stdout_text and not stderr_text:
        lines.append(
            '(no output)'
        )

    return '\n'.join(
        lines
    ).rstrip()


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

    ns = {
        '__name__': '__main__',
        '__file__': abs_path,
        '__package__': None,
        '__builtins__': __builtins__,
    }

    try:
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
        exit_code = (
            _exit_code_from_system_exit(
                e
            )
        )

    except Exception:
        exit_code = 1
        traceback.print_exc(
            file=stderr_buffer
        )

    finally:
        sys.argv = old_argv
        os.chdir(
            old_cwd
        )
        sys.path[:] = old_path

    stdout_text = (
        stdout_buffer.getvalue()
    )

    stderr_text = (
        stderr_buffer.getvalue()
    )

    result['preview'] = (
        _format_preview(
            target,
            exit_code,
            stdout_text,
            stderr_text,
        )
    )

    result['data'] = {
        'path': target,
        'exit_code': exit_code,
        'stdout': stdout_text,
        'stderr': stderr_text,
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