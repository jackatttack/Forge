# -*- coding: utf-8 -*-
"""
Portable LLM-facing Forge packet renderer.

This module is part of the environment-independent Forge protocol.

It must not import Surface or any platform-specific integration.
"""


def _packet_line_count(text):
    return len((text or '').splitlines())


def _packet_changed_ranges(before, after):
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


def _packet_collect_touched(run):
    touched = []

    for item in (run or {}).get('touched_files') or []:
        if isinstance(item, dict):
            touched.append(dict(item))

    for res in (run or {}).get('results') or []:
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
            by_rel[rel]['after'] = after
            if item.get('kind'):
                by_rel[rel]['kind'] = item.get('kind')

    return [by_rel[rel] for rel in order]


def _format_changed_files(run):
    touched = _packet_collect_touched(run)

    if not touched:
        return []

    lines = ['', 'Changed files:']

    for item in touched:
        rel = item.get('rel') or '?'
        existed_before = bool(item.get('existed_before'))
        before = item.get('before') or ''
        after = item.get('after') or ''

        if not existed_before:
            summary = 'created · %d lines' % _packet_line_count(after)
        elif before == after:
            summary = (
                'touched · %d lines · no content change'
                % _packet_line_count(after)
            )
        else:
            summary = (
                'modified · %d -> %d lines'
                % (
                    _packet_line_count(before),
                    _packet_line_count(after),
                )
            )

        lines.append('- %s — %s' % (rel, summary))

    lines.append('')
    lines.append(
        'Use DIFF current for compact details. '
        'Use DIFF current MODE: full for line-by-line diff.'
    )

    return lines


def format_packet(run):
    """Return the complete deterministic AI-facing Forge packet."""
    run = run or {}

    lines = ['=== FORGE RUN ===']

    if run.get('stamp'):
        lines.append('Run: ' + str(run.get('stamp')))

    lines.append('Mode: ' + str(run.get('mode') or 'dev'))
    lines.append('Status: ' + str(run.get('status') or 'UNKNOWN'))

    errors = run.get('errors') or []

    if errors:
        lines.append('')
        lines.append('Errors:')

        for err in errors:
            lines.append('- ' + str(err))

    lines.append('')
    lines.append('Ops:')

    results = run.get('results') or []

    if not results:
        lines.append('- none')
    else:
        for result in results:
            line = '- %s | %s | %s' % (
                result.get('status') or 'UNKNOWN',
                result.get('op') or '?',
                result.get('target') or '?',
            )

            if result.get('message'):
                line += ' :: ' + str(result.get('message'))

            lines.append(line)

    changed = _format_changed_files(run)

    if changed:
        lines.extend(changed)

    hinted = [
        hint
        for hint in (
            run.get('parse_hints')
            or []
        )
        if (
            isinstance(
                hint,
                dict,
            )
            and hint.get(
                'hint'
            )
        )
    ]

    hinted.extend([
        result
        for result in results
        if result.get('hint')
    ])

    if hinted:
        lines.append('')
        lines.append('=== HINTS ===')

        for result in hinted:
            lines.append(
                '%s %s'
                % (
                    result.get('op') or '?',
                    result.get('target') or '?',
                )
            )
            lines.append(
                str(result.get('hint')).rstrip()
            )

    previews = [
        result
        for result in results
        if result.get('preview')
    ]

    if previews:
        lines.append('')
        lines.append('=== PREVIEW ===')

        for result in previews:
            lines.append(
                str(result.get('preview')).rstrip()
            )

    return '\n'.join(lines).rstrip() + '\n'