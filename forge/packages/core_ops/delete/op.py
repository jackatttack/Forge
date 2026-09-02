# -*- coding: utf-8 -*-
"""
DELETE reboot op.

Public deletion verb for Forge.

DELETE removes existing things deliberately:
- whole files
- explicit file line ranges
- exact old text blocks

AST deletion can be added later once the semantics are proven.
"""

import os

from forge.core.file_safety import read_text, record_touched, safe_target, touched_file, write_text


SPEC = {
    'name': 'DELETE',
    'target_kind': 'path',
    'body_mode': 'optional',
    'allowed_directives': set(['CONFIRM', 'LINES', 'OCCURRENCE', 'ALL']),
    'required_directives': set(),
}

HELP = {
    'summary': 'Delete a file, explicit file line range, or exact text block.',
    'minimal_example': [
        'DELETE scratch/example.txt',
        '',
        'DELETE docs/example.txt',
        'LINES: 12-15',
        '',
        'DELETE docs/example.txt',
        'BEGIN_OLD',
        'exact text to remove',
        'END_OLD',
        '',
        'DELETE docs/example.txt',
        'ALL: yes',
        'CONFIRM: yes',
        'BEGIN_OLD',
        'repeated exact text',
        'END_OLD',
    ],
}


HINTS = {
    '_max_hints': 1,
    'failed_compile': {
        'message': 'The deletion would break the Python file, so nothing was written.',
        'why': 'Forge compiles the result before writing. Deleting these lines would leave invalid Python behind.',
        'next': [
            'READ the surrounding code; the range may cut a construct in half.',
            'Widen or narrow LINES / the OLD block to remove a complete construct.',
        ],
    },
    'all: yes requires confirm': {
        'message': 'DELETE with ALL: yes requires CONFIRM: yes.',
        'why': 'ALL expands one exact-block deletion into every matching block, so Forge requires explicit acknowledgement of the broader destructive scope.',
        'example': [
            'DELETE docs/example.txt',
            'ALL: yes',
            'CONFIRM: yes',
            'BEGIN_OLD',
            'repeated exact text',
            'END_OLD',
        ],
        'next': [
            'Use OCCURRENCE: N instead when only one repeated match should be removed.',
            'Use ALL: yes only when every exact match is intentionally being deleted.',
        ],
    },
    'not found': {
        'message': 'DELETE target was not found.',
        'why': 'The path may be wrong, the file may already be gone, or the OLD block did not match.',
        'example': [
            'READ docs/example.txt',
            '',
            'DELETE docs/example.txt',
        ],
        'next': [
            'Check the path with MAP or READ.',
            'For block deletion, copy OLD text exactly from READ output.',
        ],
    },
}


def _parse_bool(value):
    return str(value or '').strip().lower() in ('1', 'yes', 'y', 'true', 'on', 'all')


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _parse_lines(value):
    text = str(value or '').strip()
    if '-' not in text:
        return None

    left, _sep, right = text.partition('-')
    try:
        return int(left.strip()), int(right.strip())
    except Exception:
        return None


def _has_old_block(parsed_op):
    return 'OLD' in (parsed_op.get('blocks') or {})


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    blocks = parsed_op.get('blocks') or {}

    if not target:
        errors.append('DELETE requires a target path')

    if (
        _parse_bool(directives.get('ALL'))
        and str(directives.get('CONFIRM') or '').strip().lower() != 'yes'
    ):
        errors.append('DELETE ALL: yes requires CONFIRM: yes')

    if '::' in target:
        errors.append('DELETE does not support AST targets yet')

    has_lines = 'LINES' in directives
    has_old = _has_old_block(parsed_op)

    if has_lines and has_old:
        errors.append('DELETE cannot use both LINES and BEGIN_OLD')

    if has_lines:
        parsed = _parse_lines(directives.get('LINES'))
        if not parsed:
            errors.append('DELETE LINES must be start-end')
        else:
            start, end = parsed
            if start < 1 or end < start:
                errors.append('Invalid DELETE LINES range')

    if has_old:
        old = blocks.get('OLD')
        if old is None:
            errors.append('DELETE block mode requires BEGIN_OLD / END_OLD')
        elif old == '':
            errors.append('DELETE OLD block must not be empty')

        if 'OCCURRENCE' in directives:
            n = _as_int(directives.get('OCCURRENCE'), 0)
            if n < 1:
                errors.append('DELETE OCCURRENCE must be an integer >= 1')

    return errors


def _replace_range_with_empty(before, start, end):
    lines = before.splitlines(True)
    total = len(lines)

    if end > total:
        return None, 'LINES out of range: file has %d lines' % total

    out = lines[:start - 1] + lines[end:]

    if before and not before.endswith('\n') and out:
        out[-1] = out[-1].rstrip('\n')

    return ''.join(out), None


def _execute_file_delete(ctx, target, result):
    root, abs_path, err = safe_target(ctx, target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    if not os.path.exists(abs_path):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'File not found: ' + target
        return

    if not os.path.isfile(abs_path):
        result['status'] = 'FAILED_IO'
        result['message'] = 'Target exists but is not a file: ' + target
        return

    before = read_text(abs_path)
    os.remove(abs_path)

    touched = touched_file(target, before, '', existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Deleted file: ' + target
    result['preview'] = 'DELETE %s\nmode: file' % target
    result['file'] = target
    result['data'] = {'path': target, 'mode': 'file', 'deleted': True}


def _execute_lines_delete(ctx, target, parsed_op, result):
    root, abs_path, err = safe_target(ctx, target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    if not os.path.isfile(abs_path):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'File not found: ' + target
        return

    before = read_text(abs_path)
    start, end = _parse_lines((parsed_op.get('directives') or {}).get('LINES'))
    after, err = _replace_range_with_empty(before, start, end)
    if err:
        result['status'] = 'FAILED_PARSE'
        result['message'] = err
        return

    from forge.core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(abs_path, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Delete refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return

    touched = touched_file(target, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Deleted lines %d-%d in %s' % (start, end, target)
    result['preview'] = 'DELETE %s\nmode: lines\nLINES: %d-%d' % (target, start, end)
    result['file'] = target
    result['data'] = {'path': target, 'mode': 'lines', 'start': start, 'end': end}


def _execute_block_delete(ctx, target, parsed_op, result):
    root, abs_path, err = safe_target(ctx, target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    if not os.path.isfile(abs_path):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'File not found: ' + target
        return

    directives = parsed_op.get('directives') or {}
    blocks = parsed_op.get('blocks') or {}
    old = blocks.get('OLD')

    before = read_text(abs_path)
    count = before.count(old)

    if count == 0:
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'OLD block matched 0 times'
        return

    delete_all = _parse_bool(directives.get('ALL'))
    occurrence = _as_int(directives.get('OCCURRENCE'), 1)

    if delete_all:
        after = before.replace(old, '')
        deleted = count
    else:
        if occurrence > count:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'OCCURRENCE %d out of range; OLD block matched %d times' % (occurrence, count)
            return

        if count > 1 and 'OCCURRENCE' not in directives:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'OLD block matched %d times; use OCCURRENCE: N or ALL: yes' % count
            return

        parts = before.split(old)
        after = old.join(parts[:occurrence]) + old.join(parts[occurrence:])
        deleted = 1

    from forge.core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(abs_path, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Delete refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return

    touched = touched_file(target, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Deleted %d block(s) in %s' % (deleted, target)
    result['preview'] = 'DELETE %s\nmode: block\nblocks deleted: %d' % (target, deleted)
    result['file'] = target
    result['data'] = {'path': target, 'mode': 'block', 'deleted': deleted, 'matches': count}


def execute(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if 'LINES' in directives:
        _execute_lines_delete(ctx, target, parsed_op, result)
    elif _has_old_block(parsed_op):
        _execute_block_delete(ctx, target, parsed_op, result)
    else:
        _execute_file_delete(ctx, target, result)
