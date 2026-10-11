# -*- coding: utf-8 -*-
"""
DIFF operation.

Shows the stored change for a run, then shows current disk drift when the file
has changed again since the run was stored.

Recovery model:
    before-run -> after-run -> current-disk
"""

import os


SPEC = {
    'name': 'DIFF',
    'target_kind': 'none',
    'body_mode': 'forbidden',
    'allowed_directives': set(['ARGS', 'MODE']),
    'required_directives': set(),
}

HELP = {
    'summary': 'Review touched file changes compactly by default, with full line diff on request.',
    'brief': (
        'DIFF current, DIFF latest or DIFF <run stamp> · compact by default, '
        'MODE: full for the line-by-line diff.'
    ),
    'minimal_example': [
        'DIFF current',
        '',
        'DIFF current',
        'MODE: full',
        '',
        'DIFF latest',
        '',
        'DIFF 20260511_120000',
        'MODE: full',
    ],
    'directives': {
        'MODE': (
            'Output detail: compact or full. '
            'The default is compact.'
        ),
    },
    'internal_directives': [
        'ARGS',
    ],
    'common_failures': [
        'Using DIFF when the run packet already contains enough information.',
        'Using MODE: full for large documentation changes and creating noisy packets.',
        'Expecting DIFF to mutate or restore files. Use REVERT for recovery.',
    ],
    'safe_usage': [
        'Prefer compact default mode for normal review.',
        'Use MODE: full only when exact line-by-line detail matters.',
        'Use DIFF current inside a bundle to review changes made earlier in that same bundle.',
        'Use DIFF latest or DIFF <stamp> for stored runs.',
    ],
    'related_ops': ['FORGE', 'REVERT', 'READ'],
}


HINTS = {
    '_max_hints': 1,
    'run': {
        'message': 'DIFF needs a stored run id.',
        'why': 'Diff compares a run snapshot against the current disk state.',
        'example': [
            'RUNS latest',
            '',
            'DIFF 20260511_120000',
        ],
        'next': [
            'Run RUNS latest or RUNS list.',
            'Copy the stamp exactly into DIFF.',
        ],
    },
}

def validate(parsed_op):
    return []


def _args(parsed_op):
    return ((parsed_op.get('directives') or {}).get('ARGS') or parsed_op.get('target') or '').strip()


def _mode(parsed_op):
    directives = (parsed_op or {}).get('directives') or {}
    mode = str(directives.get('MODE') or '').strip().lower()
    if mode:
        return mode

    args = _args(parsed_op)
    parts = [p.strip().lower() for p in args.split() if p.strip()]
    for part in parts[1:]:
        if part in ('full', 'compact'):
            return part

    return 'compact'


def _stamp_arg(parsed_op):
    args = _args(parsed_op)
    parts = [p.strip() for p in args.split() if p.strip()]
    if not parts:
        return ''
    return parts[0]


# Lines of unchanged context shown around each change in a full diff.
DIFF_CONTEXT_LINES = 2

# Most diff lines shown per file, so a whole-file rewrite cannot flood the
# packet. READ the file for anything beyond this.
MAX_DIFF_LINES = 200


def _diff_lines(before, after, context=DIFF_CONTEXT_LINES):
    """
    Real line diff of before -> after, as numbered hunks.

    Uses difflib, so an inserted line shows as one '+' line instead of
    shifting every later line into a change. Each hunk starts with a
    unified-style header; removed lines carry their old line number, added
    and context lines their new one. Output is capped at MAX_DIFF_LINES.
    """
    import difflib

    before_lines = (before or '').splitlines()
    after_lines = (after or '').splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)

    out = []
    for group in matcher.get_grouped_opcodes(context):
        first, last = group[0], group[-1]
        out.append('  @@ -%d,%d +%d,%d @@' % (
            first[1] + 1, last[2] - first[1],
            first[3] + 1, last[4] - first[3],
        ))
        for tag, i1, i2, j1, j2 in group:
            if tag == 'equal':
                for offset, text in enumerate(after_lines[j1:j2]):
                    out.append('    %04d  %s' % (j1 + offset + 1, text))
                continue
            for offset, text in enumerate(before_lines[i1:i2]):
                out.append('  - %04d  %s' % (i1 + offset + 1, text))
            for offset, text in enumerate(after_lines[j1:j2]):
                out.append('  + %04d  %s' % (j1 + offset + 1, text))

    if len(out) > MAX_DIFF_LINES:
        hidden = len(out) - MAX_DIFF_LINES
        out = out[:MAX_DIFF_LINES] + [
            '  ... %d more diff lines; READ the file for the rest' % hidden
        ]
    return out


def _read_current(root, rel):
    path = os.path.join(root, rel)
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(), True
    except Exception:
        return '', False


def _collect_current_touched(run):
    from forge.core.content_records import collect_changes
    return collect_changes(run)


def _line_count(text):
    return len((text or '').splitlines())


def _changed_ranges(before, after):
    """
    Compact summary of real changes, located in the new file.

    "51-54 (+4 -3), 99 (+1)" means lines 51-54 now hold 4 lines that
    replaced 3, and line 99 is one new line. A pure deletion has no lines
    of its own in the new file, so it reads "after 120 (-2)". Returns
    "none" when nothing changed.
    """
    import difflib

    before_lines = (before or '').splitlines()
    after_lines = (after or '').splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)

    parts = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        added = j2 - j1
        removed = i2 - i1
        if added == 0:
            where = 'after %d' % j1
        elif added == 1:
            where = '%d' % (j1 + 1)
        else:
            where = '%d-%d' % (j1 + 1, j2)
        counts = ' '.join(
            text for text in (
                '+%d' % added if added else '',
                '-%d' % removed if removed else '',
            ) if text
        )
        parts.append('%s (%s)' % (where, counts))

    return ', '.join(parts) or 'none'


def _render_touched_full(root, label, touched):
    lines = ['DIFF %s' % label]

    if not touched:
        lines.append('(no touched files)')
        return lines

    for item in touched:
        rel = item.get('rel') or '?'
        existed_before = bool(item.get('existed_before'))
        before = item.get('before') or ''
        after = item.get('after') or ''
        current, current_exists = _read_current(root, rel)

        lines.append('')
        lines.append(rel)

        if existed_before:
            lines.append('  stored change: before -> after')
        else:
            lines.append('  stored change: created by run')

        stored_diff = _diff_lines(before, after)
        if stored_diff:
            lines.extend(stored_diff)
        else:
            lines.append('  (no stored content change)')

        if current_exists:
            if current != after:
                lines.append('  current disk drift:')
                drift = _diff_lines(after, current)
                if drift:
                    lines.extend(drift)
                else:
                    lines.append('  (current differs, but no line diff emitted)')
        else:
            if after:
                lines.append('  current disk drift:')
                lines.append('  file missing on disk')

    return lines


def _render_touched_compact(root, label, touched):
    lines = ['DIFF %s' % label, 'MODE=compact']

    if not touched:
        lines.append('(no touched files)')
        return lines

    lines.append('%d touched file(s)' % len(touched))

    for item in touched:
        rel = item.get('rel') or '?'
        existed_before = bool(item.get('existed_before'))
        before = item.get('before') or ''
        after = item.get('after') or ''
        current, current_exists = _read_current(root, rel)

        lines.append('')
        lines.append(rel)

        if not existed_before:
            lines.append('  stored: created by run')
            lines.append('  lines: 0 -> %d' % _line_count(after))
        elif before == after:
            lines.append('  stored: touched, no content change')
            lines.append('  lines: %d' % _line_count(after))
        else:
            lines.append('  stored: modified by run')
            lines.append('  lines: %d -> %d' % (_line_count(before), _line_count(after)))
            lines.append('  changed lines: %s' % _changed_ranges(before, after))

        if current_exists:
            if current != after:
                lines.append('  drift: yes')
                lines.append('  current lines: %d' % _line_count(current))
                lines.append('  drift lines: %s' % _changed_ranges(after, current))
            else:
                lines.append('  drift: no')
        else:
            if after:
                lines.append('  drift: file missing on disk')
            else:
                lines.append('  drift: no current file')

    lines.append('')
    lines.append('Use MODE: full for line-by-line diff output.')
    return lines


def _render_content_item(root, item, mode):
    """Render byte-aware states without loading binary payloads for display."""
    from forge.core.content_records import state_content
    from forge.core.content_recovery import disk_state
    from forge.core.file_content import INLINE_TEXT_BYTES

    relative = item['rel']
    root_name = item.get('root') or ''
    shown = '%s:%s' % (root_name, relative) if root_name else relative
    before = state_content(item, 'before')
    after = state_content(item, 'after')
    existed_before = bool(item.get('existed_before'))
    existed_after = item.get('existed_after')
    if existed_after is None:
        existed_after = True
    file_backed = any(
        content.get('encoding') == 'blob' for content in (before, after)
    )

    lines = ['', shown]
    if not existed_before and not existed_after:
        action = 'created and removed; no net change'
    elif not existed_after:
        action = 'deleted by run'
    elif not existed_before:
        action = 'created by run'
    elif before['sha256'] == after['sha256']:
        action = 'touched, no content change'
    else:
        action = 'modified by run'
    lines.append('  stored: ' + action)

    if file_backed:
        lines.extend([
            '  content: binary/large file',
            '  bytes: %d -> %d' % (before['size'], after['size']),
            '  SHA-256 before: ' + before['sha256'],
            '  SHA-256 after:  ' + after['sha256'],
        ])
    else:
        old_text = before['text']
        new_text = after['text']
        lines.append('  lines: %d -> %d' % (
            _line_count(old_text), _line_count(new_text),
        ))
        if mode == 'full':
            lines.extend(_diff_lines(old_text, new_text))
        elif old_text != new_text:
            lines.append('  changed lines: ' + _changed_ranges(old_text, new_text))

    if not root:
        lines.append('  drift: recorded root unavailable')
        return lines
    try:
        path, exists, size, checksum, identity = disk_state(root, relative)
    except (OSError, ValueError) as error:
        lines.append('  drift: unreadable or unsafe target: ' + str(error))
        return lines

    if exists != existed_after:
        lines.append('  drift: file appeared on disk' if exists
                     else '  drift: file missing on disk')
    elif not exists or (size, checksum) == (after['size'], after['sha256']):
        lines.append('  drift: no')
        return lines
    else:
        lines.append('  drift: yes')

    if exists:
        lines.append('  current bytes: %d' % size)
        lines.append('  current SHA-256: ' + checksum)
        if not file_backed and size <= INLINE_TEXT_BYTES:
            try:
                with open(path, 'rb') as handle:
                    current_text = handle.read().decode('utf-8')
                if '\x00' not in current_text:
                    if mode == 'full':
                        lines.extend(_diff_lines(after['text'], current_text))
                    else:
                        lines.append('  drift lines: ' + _changed_ranges(
                            after['text'], current_text,
                        ))
            except (OSError, UnicodeError):
                pass
    return lines


def _render_touched(root, label, touched, mode='compact', roots=None):
    mode = str(mode or '').strip().lower()
    modern = any(
        item.get('root') or 'before_content' in item or 'after_content' in item
        for item in touched
    )
    if not modern:
        if mode == 'full':
            return _render_touched_full(root, label, touched)
        return _render_touched_compact(root, label, touched)

    roots = roots or {}
    lines = ['DIFF %s' % label]
    if mode != 'full':
        lines.append('MODE=compact')
    lines.append('%d touched file(s)' % len(touched))
    for item in touched:
        entry_root = roots.get(item['root']) if item.get('root') else root
        lines.extend(_render_content_item(entry_root, item, mode))
    if mode != 'full':
        lines.extend(['', 'Use MODE: full for text line diffs; binary files show byte metadata.'])
    return lines


def execute(ctx, parsed_op, result):
    from forge.core.run_storage import (
        list_runs,
        read_manifest,
    )

    environment = (
        (ctx or {}).get(
            'environment'
        )
        or {}
    )

    root = (
        environment.get(
            'project_root'
        )
        or ctx.get(
            'project_root'
        )
        or os.getcwd()
    )

    run_mode = str(
        (
            (ctx.get('run') or {}).get(
                'mode'
            )
            or ctx.get('mode')
            or 'dev'
        )
    )

    stamp = _stamp_arg(
        parsed_op
    )

    diff_mode = _mode(
        parsed_op
    )

    if diff_mode not in (
        'compact',
        'full',
    ):
        result['status'] = (
            'FAILED_PARSE'
        )
        result['message'] = (
            'DIFF MODE must be compact or full, got: '
            + str(diff_mode)
        )
        return

    if stamp == 'current':
        touched = (
            _collect_current_touched(
                ctx.get('run')
                or {}
            )
        )

        lines = _render_touched(
            root,
            'current',
            touched,
            mode=diff_mode,
            roots=environment.get('roots') or {},
        )

        result['status'] = 'APPLIED'
        result['message'] = (
            '%d current file(s) diffed'
            % len(touched)
        )
        result['preview'] = (
            '\n'.join(lines).rstrip()
        )
        result['data'] = {
            'mode': 'current',
            'diff_mode': diff_mode,
            'touched': touched,
        }
        return

    if not stamp or stamp == 'latest':
        runs = list_runs(
            root,
            limit=1,
            mode=run_mode,
            environment=environment,
        )

        if not runs:
            result['status'] = 'APPLIED'
            result['message'] = (
                'No runs found'
            )
            result['preview'] = (
                'DIFF [no runs]'
            )
            return

        stamp = runs[0]

    manifest, err = read_manifest(
        root,
        stamp,
        mode=run_mode,
        environment=environment,
    )

    if err:
        result['status'] = (
            'FAILED_NOT_FOUND'
        )
        result['message'] = err
        return

    touched = (
        manifest.get('touched')
        or []
    )

    lines = _render_touched(
        root,
        stamp,
        touched,
        mode=diff_mode,
        roots=manifest.get('roots') or {},
    )

    result['status'] = 'APPLIED'
    result['message'] = (
        '%d file(s) diffed'
        % len(touched)
    )
    result['preview'] = (
        '\n'.join(lines).rstrip()
    )
    result['data'] = {
        'mode': 'stored',
        'diff_mode': diff_mode,
        'stamp': stamp,
        'touched': touched,
    }
