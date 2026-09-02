# -*- coding: utf-8 -*-
"""
Reboot core guard.

Protects the reboot kernel from accidental self-modification.

The rule is intentionally simple:
- read-only ops may inspect anything
- mutating ops that touch protected reboot core paths require CONFIRM: yes
- blocked ops do not execute
"""

import os


MUTATING_OPS = set([
    'BRANCH',
    'CLIPBOARD',
    'COPY',
    'DELETE',
    'INSERT',
    'MOVE',
    'PIP',
    'REPLACE',
    'REVERT',
    'RUN',
    'SYNC_EXPORT',
    'URL',
    'WRITE',
])


PROTECTED_PREFIXES = [
    'forge/entry.py',
    'forge/forge/core/',
    'forge/forge/packages/core_ops/branch/',
    'forge/forge/packages/core_ops/revert/',
    'forge/forge/packages/core_ops/diff/',
]


def _norm_rel(path):
    text = str(path or '').strip().replace('\\', '/')
    while text.startswith('./'):
        text = text[2:]
    return text


def is_mutating_op(op_name):
    return str(op_name or '').upper() in MUTATING_OPS


def target_is_protected(target):
    rel = _norm_rel(target)
    if not rel:
        return False

    for prefix in PROTECTED_PREFIXES:
        p = _norm_rel(prefix)
        if p.endswith('/'):
            if rel.startswith(p):
                return True
        elif rel == p:
            return True

    return False


def has_confirm(parsed_op):
    directives = (parsed_op or {}).get('directives') or {}
    value = str(directives.get('CONFIRM') or '').strip().lower()
    return value in (
        'yes',
        'true',
        '1',
        'confirm',
        'overwrite',
    )


def needs_confirm(parsed_op):
    op_name = str((parsed_op or {}).get('op') or '').upper()
    target = (parsed_op or {}).get('target') or ''

    if not is_mutating_op(op_name):
        return False

    return target_is_protected(target)


def guard_message(parsed_op):
    op_name = str((parsed_op or {}).get('op') or '?').upper()
    target = str((parsed_op or {}).get('target') or '?')
    return (
        'Core guard blocked %s on protected target: %s\n'
        'WHY: reboot kernel/core files require explicit confirmation before mutation.\n'
        'NEXT:\n'
        '- Inspect first with MAP / READ / FORGE help.\n'
        '- Add CONFIRM only when the protected edit is intentional.\n'
        '- Create a BRANCH before confirmed core edits.'
    ) % (op_name, target)


def check(parsed_op):
    if needs_confirm(parsed_op) and not has_confirm(parsed_op):
        return False, guard_message(parsed_op)
    return True, ''
