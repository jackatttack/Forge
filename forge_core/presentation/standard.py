# -*- coding: utf-8 -*-
"""
Standard text presentation for portable Forge.

The canonical packet remains untouched. Standard presentation appends one
small human summary after it.

This module is deliberately platform-independent.
"""


def _counts(run):
    applied = 0
    skipped = 0
    failed = 0

    for result in (run or {}).get('results') or []:
        status = str(
            result.get('status')
            or ''
        ).upper()

        if status == 'APPLIED':
            applied += 1
        elif status.startswith('SKIPPED'):
            skipped += 1
        else:
            failed += 1

    return applied, skipped, failed


def _changed_files(run):
    seen = set()

    for item in (run or {}).get('touched_files') or []:
        if not isinstance(item, dict):
            continue

        path = str(
            item.get('rel')
            or item.get('file')
            or ''
        ).strip()

        if path:
            seen.add(path)

    for result in (run or {}).get('results') or []:
        for item in result.get('touched') or []:
            if not isinstance(item, dict):
                continue

            path = str(
                item.get('rel')
                or item.get('file')
                or ''
            ).strip()

            if path:
                seen.add(path)

    return sorted(seen)


def format_summary(run):
    """Return the small standard human summary."""
    run = run or {}

    applied, skipped, failed = _counts(
        run
    )

    changed = _changed_files(
        run
    )

    lines = [
        '=== FORGE SUMMARY ===',
        'Status: %s'
        % str(
            run.get('status')
            or 'UNKNOWN'
        ).upper(),
        'Ops: %d applied · %d skipped · %d failed'
        % (
            applied,
            skipped,
            failed,
        ),
        'Changed: %d file%s'
        % (
            len(changed),
            '' if len(changed) == 1 else 's',
        ),
    ]

    errors = run.get('errors') or []

    if errors:
        lines.append(
            'Errors: %d'
            % len(errors)
        )

    return (
        '\n'.join(lines).rstrip()
        + '\n'
    )


def render_standard(run):
    """
    Return canonical packet followed by the standard human summary.

    run['packet'] is never modified.
    """
    run = run or {}

    packet = str(
        run.get('packet')
        or ''
    )

    summary = format_summary(
        run
    )

    if not packet:
        return summary

    if not packet.endswith('\n'):
        packet += '\n'

    return (
        packet
        + '\n'
        + summary
    )