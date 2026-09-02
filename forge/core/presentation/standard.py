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



def _packet_bytes(run):
    value = (run or {}).get(
        'packet_bytes'
    )

    if value is not None:
        try:
            return max(
                0,
                int(
                    value
                ),
            )
        except Exception:
            pass

    packet = str(
        (run or {}).get(
            'packet'
        )
        or ''
    )

    return len(
        packet.encode(
            'utf-8'
        )
    )


def _format_bytes(value):
    try:
        value = max(
            0,
            int(
                value
            ),
        )
    except Exception:
        value = 0

    if value < 1024:
        return '%d B' % value

    if value < (
        1024
        * 1024
    ):
        return '%.1f KB' % (
            value
            / 1024.0
        )

    return '%.1f MB' % (
        value
        / (
            1024.0
            * 1024.0
        )
    )

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
        'Packet: %s'
        % _format_bytes(
            _packet_bytes(
                run
            )
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