# -*- coding: utf-8 -*-
"""
REPLACE reboot op.

Unified replacement op for the reboot.

Supported shapes:

1. AST replacement:
   REPLACE file.py::target

2. Plain file range replacement:
   REPLACE docs/file.txt
   LINES: 12-20

3. Exact block replacement:
   REPLACE docs/file.txt
   BEGIN_OLD
   old exact text
   END_OLD
   BEGIN_NEW
   new exact text
   END_NEW

This is the single public surgical replacement surface. More modes can be added
later without changing the user-facing verb.
"""

import os

from forge.core.ast_tools import resolve_ast_target
from forge.core.file_safety import (
    read_text,
    record_touched,
    safe_target,
    touched_file,
    write_text,
)
from forge.core.source_edit import replace_line_range


SPEC = {
    'name': 'REPLACE',
    'target_kind': 'path',
    'body_mode': 'optional',
    'allowed_directives': set(['ALL', 'CONFIRM', 'LINES', 'OCCURRENCE']),
    'required_directives': set(),
}

HELP = {
    'summary': 'Replace an AST target, explicit file range, or exact old/new block.',
    'minimal_example': [
        'READ app.py',
        'TARGETS: yes',
        '',
        'READ app.py::main',
        '',
        'REPLACE app.py::main',
        'BEGIN_BODY',
        'def main():',
        '    return True',
        'END_BODY',
        '',
        'READ docs/example.txt',
        'LINES: 10-20',
        '',
        'REPLACE docs/example.txt',
        'LINES: 12-15',
        'BEGIN_BODY',
        'replacement text',
        'END_BODY',
        '',
        'REPLACE docs/example.txt',
        'BEGIN_OLD',
        'old exact text',
        'END_OLD',
        'BEGIN_NEW',
        'new exact text',
        'END_NEW',
    ],
}


HINTS = {
    '_max_hints': 1,
    'failed_compile': {
        'message': 'The replacement would break the Python file, so nothing was written.',
        'why': 'Forge compiles the patched result before writing. The error names the failing line in the would-be result.',
        'next': [
            'Check the body for unterminated strings, unbalanced brackets, or bad indentation.',
            'READ the target again and rebuild the body from the current source.',
        ],
    },
    'failed_ambiguous': {
        'message': 'The target name matched more than one definition in the file.',
        'why': 'Patching the first match silently would risk editing dead code. The message lists the matching line numbers.',
        'next': [
            'READ the file and decide which definition is live.',
            'Use REPLACE with LINES: start-end to target the exact range.',
            'Consider removing the duplicate; the later definition wins at runtime.',
        ],
    },
    'body': {
        'message': 'REPLACE needs replacement content.',
        'why': 'AST and line-range replacement use BEGIN_BODY. Exact block replacement uses BEGIN_OLD and BEGIN_NEW.',
        'example': [
            'READ app.py::main',
            '',
            'REPLACE app.py::main',
            'BEGIN_BODY',
            'def main():',
            '    return True',
            'END_BODY',
            '',
            'REPLACE docs/example.txt',
            'BEGIN_OLD',
            'old text',
            'END_OLD',
            'BEGIN_NEW',
            'new text',
            'END_NEW',
        ],
        'next': [
            'READ the target first.',
            'For AST replacement, copy the full replacement function/method/class.',
            'For file ranges, use LINES: start-end plus BEGIN_BODY.',
            'For exact block replacement, use BEGIN_OLD and BEGIN_NEW.',
        ],
    },
    'mode': {
        'message': 'REPLACE could not choose a replacement mode.',
        'why': 'Use file.py::target, LINES: start-end, or BEGIN_OLD/BEGIN_NEW blocks.',
        'example': [
            'REPLACE app.py::main',
            'BEGIN_BODY',
            'def main():',
            '    return True',
            'END_BODY',
            '',
            'REPLACE docs/example.txt',
            'LINES: 12-15',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
            '',
            'REPLACE docs/example.txt',
            'BEGIN_OLD',
            'old',
            'END_OLD',
            'BEGIN_NEW',
            'new',
            'END_NEW',
        ],
        'next': [
            'Use READ with TARGETS: yes for AST edits.',
            'Use READ with LINES before line-range edits.',
            'Use exact OLD/NEW blocks when line numbers are awkward.',
        ],
    },
    'not found': {
        'message': 'REPLACE target was not found.',
        'why': 'The target syntax may be wrong, the file may have drifted, the path may not exist, or OLD text did not match exactly.',
        'example': [
            'READ app.py',
            'TARGETS: yes',
            '',
            'READ app.py::main',
            '',
            'READ docs/example.txt',
            'LINES: 20-40',
        ],
        'next': [
            'Check the path with MAP or READ.',
            'For AST targets, run READ with TARGETS: yes and copy the exact target.',
            'For OLD block failures, READ the current file and copy the exact current text again.',
        ],
    },
    'lines': {
        'message': 'REPLACE line range needs current, valid line numbers.',
        'why': 'Line ranges are based on the file as it exists at the moment this op runs. If earlier edits changed the file, old line numbers may drift or go out of range.',
        'example': [
            'READ docs/example.txt',
            'LINES: 1-40',
            '',
            'REPLACE docs/example.txt',
            'LINES: 12-15',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ],
        'next': [
            'READ the file with line numbers.',
            'Use LINES: start-end for the current inclusive range.',
            'When doing multiple line-range REPLACEs in one file, apply later line numbers first so earlier edits do not shift later targets.',
            'Use BEGIN_OLD/BEGIN_NEW when line numbers may drift.',
        ],
    },
    'block': {
        'message': 'REPLACE exact block matching needs a deliberate OLD/NEW match.',
        'why': 'The OLD block must match the current file exactly. If it matches 0 times, the text has drifted. If it matches more than once, Forge refuses to guess.',
        'example': [
            'READ docs/example.txt',
            '',
            'REPLACE docs/example.txt',
            'OCCURRENCE: 2',
            'BEGIN_OLD',
            'repeated text',
            'END_OLD',
            'BEGIN_NEW',
            'replacement text',
            'END_NEW',
            '',
            'REPLACE docs/example.txt',
            'ALL: yes',
            'BEGIN_OLD',
            'old text',
            'END_OLD',
            'BEGIN_NEW',
            'new text',
            'END_NEW',
        ],
        'next': [
            'If OLD matched 0 times, READ the file and copy the exact current text again.',
            'If OLD matched more than once, make the OLD block more specific or use OCCURRENCE: N deliberately.',
            'Use ALL: yes only when replacing every matching block is intentional.',
            'Watch whitespace and blank lines; exact block mode is literal.',
        ],
    },
}


def _root(ctx):
    from forge.core.environment import path_from_ctx

    return path_from_ctx(
        ctx,
        'project_root',
    )


def _parse_lines(value):
    if isinstance(value, tuple) and len(value) == 2:
        return int(value[0]), int(value[1])

    text = str(value or '').strip()
    if '-' not in text:
        return None

    left, _sep, right = text.partition('-')
    try:
        return int(left.strip()), int(right.strip())
    except Exception:
        return None


def _parse_bool(value):
    return str(value or '').strip().lower() in ('1', 'yes', 'y', 'true', 'on', 'all')


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _has_block_pair(parsed_op):
    blocks = parsed_op.get('blocks') or {}
    return 'OLD' in blocks or 'NEW' in blocks


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    body = parsed_op.get('body') or ''
    blocks = parsed_op.get('blocks') or {}

    if not target:
        errors.append('REPLACE requires a target')

    is_ast = '::' in target
    has_lines = 'LINES' in directives
    has_block = _has_block_pair(parsed_op)

    if is_ast or has_lines:
        if not body:
            errors.append('REPLACE requires body content')
    elif has_block:
        old = blocks.get('OLD')
        new = blocks.get('NEW')

        if old is None:
            errors.append('REPLACE block mode requires BEGIN_OLD / END_OLD')
        elif old == '':
            errors.append('REPLACE OLD block must not be empty')

        if new is None:
            errors.append('REPLACE block mode requires BEGIN_NEW / END_NEW')

        if 'OCCURRENCE' in directives:
            n = _as_int(directives.get('OCCURRENCE'), 0)
            if n < 1:
                errors.append('REPLACE OCCURRENCE must be an integer >= 1')
    else:
        errors.append('Plain file REPLACE requires LINES: start-end or BEGIN_OLD/BEGIN_NEW')
        return errors

    if has_lines:
        parsed = _parse_lines(directives.get('LINES'))
        if not parsed:
            errors.append('REPLACE LINES must be start-end')
        else:
            start, end = parsed
            if start < 1 or end < start:
                errors.append('Invalid REPLACE LINES range')

    return errors


def _execute_ast(ctx, parsed_op, result):
    from forge.core.file_safety import checked_write, CompileBlocked

    root = _root(ctx)
    target = (parsed_op.get('target') or '').strip()
    body = parsed_op.get('body') or ''

    resolved = resolve_ast_target(root, target)
    if not resolved or not resolved.get('ok'):
        result['status'] = (resolved or {}).get('code') or 'FAILED_NOT_FOUND'
        result['message'] = (resolved or {}).get('error') or ('Target not found: ' + target)
        return

    file_abs = resolved.get('file_abs')
    before = read_text(file_abs)

    try:
        after = replace_line_range(
            before,
            int(resolved.get('start') or 1),
            int(resolved.get('end') or 1),
            body,
        )
    except Exception as e:
        result['status'] = 'FAILED_RUNTIME'
        result['message'] = type(e).__name__ + ': ' + str(e)
        return

    try:
        checked_write(file_abs, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Patch refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return

    try:
        rel = os.path.relpath(file_abs, root)
    except Exception:
        rel = resolved.get('file_ref') or target.split('::', 1)[0]

    touched = touched_file(rel, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Replaced %s lines %s-%s' % (
        target,
        resolved.get('start'),
        resolved.get('end'),
    )
    result['file'] = rel
    result['preview'] = '\n'.join([
        'REPLACE ' + target,
        'mode: ast',
        'file: ' + rel,
        'kind: ' + str(resolved.get('kind') or '?'),
        'lines: %s-%s' % (resolved.get('start'), resolved.get('end')),
    ])
    result['data'] = {
        'target': target,
        'path': rel,
        'kind': resolved.get('kind'),
        'start': resolved.get('start'),
        'end': resolved.get('end'),
        'mode': 'ast',
    }


def _replace_range(before, start, end, body):
    lines = before.splitlines(True)
    total = len(lines)

    if end > total:
        return None, 'LINES out of range: file has %d lines' % total

    replacement = body or ''
    replacement_lines = replacement.splitlines(True)

    if replacement and not replacement.endswith('\n'):
        replacement_lines.append('\n')

    out = lines[:start - 1] + replacement_lines + lines[end:]

    if before and not before.endswith('\n') and out:
        out[-1] = out[-1].rstrip('\n')

    return ''.join(out), None


def _execute_file_range(ctx, parsed_op, result):
    rel = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    root, abs_path, err = safe_target(ctx, rel)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    try:
        before = read_text(abs_path)
    except Exception as e:
        result['status'] = 'FAILED_IO'
        result['message'] = 'File not found or unreadable: %s: %s' % (type(e).__name__, e)
        return

    start, end = _parse_lines(directives.get('LINES'))
    after, err = _replace_range(before, start, end, parsed_op.get('body') or '')
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
            'Patch refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    except Exception as e:
        result['status'] = 'FAILED_IO'
        result['message'] = 'Could not write file: %s: %s' % (type(e).__name__, e)
        return

    touched = touched_file(rel, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Replaced lines %d-%d in %s' % (start, end, rel)
    result['preview'] = 'REPLACE %s\nmode: lines\nLINES: %d-%d' % (rel, start, end)
    result['file'] = rel
    result['data'] = {
        'path': rel,
        'start': start,
        'end': end,
        'mode': 'lines',
        'before': before,
        'after': after,
    }


def _execute_block(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    blocks = parsed_op.get('blocks') or {}
    old = blocks.get('OLD')
    new = blocks.get('NEW') or ''

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
    count = before.count(old)

    if count == 0:
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'OLD block matched 0 times'
        return

    replace_all = _parse_bool(directives.get('ALL'))
    occurrence = _as_int(directives.get('OCCURRENCE'), 1)

    if replace_all:
        after = before.replace(old, new)
        replaced = count
    else:
        if occurrence > count:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'OCCURRENCE %d out of range; OLD block matched %d times' % (
                occurrence,
                count,
            )
            return

        if count > 1 and 'OCCURRENCE' not in directives:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'OLD block matched %d times; use OCCURRENCE: N or ALL: yes' % count
            return

        parts = before.split(old)
        after = old.join(parts[:occurrence]) + new + old.join(parts[occurrence:])
        replaced = 1

    from forge.core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(abs_path, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Patch refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    touched = touched_file(target, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Replaced %d block(s) in %s' % (replaced, target)
    result['file'] = target
    result['preview'] = 'REPLACE %s\nmode: block\nreplaced: %d\nmatches: %d' % (
        target,
        replaced,
        count,
    )
    result['data'] = {
        'path': target,
        'replaced': replaced,
        'matches': count,
        'mode': 'block',
    }


def execute(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if '::' in target:
        _execute_ast(ctx, parsed_op, result)
    elif 'LINES' in directives:
        _execute_file_range(ctx, parsed_op, result)
    elif _has_block_pair(parsed_op):
        _execute_block(ctx, parsed_op, result)
    else:
        result['status'] = 'FAILED_PARSE'
        result['message'] = 'REPLACE needs file.py::target, LINES: start-end, or BEGIN_OLD/BEGIN_NEW'
