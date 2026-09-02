# -*- coding: utf-8 -*-
"""
DIFF reboot op.

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


def _diff_lines(before, after):
    before_lines = (before or '').splitlines()
    after_lines = (after or '').splitlines()
    max_len = max(len(before_lines), len(after_lines))
    out = []

    for i in range(max_len):
        b = before_lines[i] if i < len(before_lines) else None
        a = after_lines[i] if i < len(after_lines) else None
        if b == a:
            continue
        if b is not None:
            out.append('  line %d -%s' % (i + 1, b))
        if a is not None:
            out.append('  line %d +%s' % (i + 1, a))

    return out


def _read_current(root, rel):
    path = os.path.join(root, rel)
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(), True
    except Exception:
        return '', False


def _collect_current_touched(run):
    touched = []

    for item in run.get('touched_files') or []:
        if isinstance(item, dict):
            touched.append(dict(item))

    for res in run.get('results') or []:
        for item in res.get('touched') or []:
            if isinstance(item, dict):
                touched.append(dict(item))

    by_rel = {}
    order = []

    for item in touched:
        rel = str(item.get('rel') or item.get('file') or '').strip()
        if not rel:
            continue

        before = item.get('before') if item.get('before') is not None else ''
        after = item.get('after') if item.get('after') is not None else ''

        if rel not in by_rel:
            order.append(rel)
            by_rel[rel] = {
                'rel': rel,
                'kind': item.get('kind') or 'file',
                'existed_before': bool(item.get('existed_before')),
                'before': before,
                'after': after,
            }
        else:
            # A file can be patched multiple times in one run. Keep the first
            # before snapshot and the final after snapshot so current-run diff
            # reflects the aggregate change, not fake drift after the first edit.
            by_rel[rel]['after'] = after
            if item.get('kind'):
                by_rel[rel]['kind'] = item.get('kind')

    return [by_rel[rel] for rel in order]


def _line_count(text):
    return len((text or '').splitlines())


def _changed_ranges(before, after):
    before_lines = (before or '').splitlines()
    after_lines = (after or '').splitlines()
    max_len = max(len(before_lines), len(after_lines))
    nums = []

    for i in range(max_len):
        b = before_lines[i] if i < len(before_lines) else None
        a = after_lines[i] if i < len(after_lines) else None
        if b != a:
            nums.append(i + 1)

    if not nums:
        return 'none'

    ranges = []
    start = nums[0]
    prev = nums[0]

    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append((start, prev))
        start = prev = n

    ranges.append((start, prev))

    parts = []
    for a, b in ranges:
        if a == b:
            parts.append(str(a))
        else:
            parts.append('%d-%d' % (a, b))

    return ', '.join(parts)


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


def _render_touched(root, label, touched, mode='compact'):
    if str(mode or '').strip().lower() == 'full':
        return _render_touched_full(root, label, touched)
    return _render_touched_compact(root, label, touched)


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
