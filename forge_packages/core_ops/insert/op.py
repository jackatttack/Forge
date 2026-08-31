# -*- coding: utf-8 -*-
"""
INSERT reboot op.

Unified insertion op for the reboot.

Supported shapes:

1. AST sibling insert:
   INSERT file.py::target
   POSITION: before|after

2. AST body insert:
   INSERT file.py::target
   POSITION: start|end

3. AST anchored insert:
   INSERT file.py::target
   ANCHOR: some existing line
   POSITION: before|after
   INDENT: auto|same|child

4. Plain file line insert:
   INSERT docs/file.txt
   LINE: 12
   POSITION: before|after

This intentionally consolidates Forge2's INSERT_BEFORE / INSERT_AFTER /
INSERT_INTO / APPEND_INTO / PREPEND_INTO / INSERT_FILE_LINE family into one
smaller surface.
"""

import os

from forge_core.ast_tools import resolve_ast_target, read_source
from forge_core.file_safety import safe_target, read_text, write_text, touched_file, record_touched
from forge_core.source_edit import insert_after_line, line_indent


SPEC = {
    'name': 'INSERT',
    'target_kind': 'path',
    'body_mode': 'required',
    'allowed_directives': set([
        'ANCHOR',
        'CONFIRM',
        'EXPECT',
        'INDENT',
        'LINE',
        'MATCH',
        'OCCURRENCE',
        'POSITION',
    ]),
    'required_directives': set(),
}

HELP = {
    'summary': 'Insert text or code into a file or resolved AST target.',
    'minimal_example': [
        'INSERT app.py::main',
        'POSITION: end',
        'BEGIN_BODY',
        'print("done")',
        'END_BODY',
        '',
        'INSERT docs/example.txt',
        'LINE: 4',
        'POSITION: after',
        'BEGIN_BODY',
        'new line',
        'END_BODY',
        '',
        'INSERT app.py::main',
        'ANCHOR: if ready:',
        'POSITION: after',
        'INDENT: child',
        'BEGIN_BODY',
        'run()',
        'END_BODY',
        '',
        'INSERT app.py::existing_function',
        'POSITION: after',
        'BEGIN_BODY',
        '',
        '',
        'def new_helper():',
        '    return True',
        'END_BODY',
    ],
}


HINTS = {
    '_max_hints': 1,
    'failed_compile': {
        'message': 'The insert would break the Python file, so nothing was written.',
        'why': 'Forge compiles the result before writing. The error names the failing line in the would-be result.',
        'next': [
            'Check the body for unterminated strings, unbalanced brackets, or bad indentation.',
            'Check INDENT/POSITION: a wrong indent level can make valid code invalid in context.',
        ],
    },
    'failed_ambiguous': {
        'message': 'The target name matched more than one definition in the file.',
        'why': 'Inserting at the first match silently would risk anchoring on dead code. The message lists the matching lines.',
        'next': [
            'READ the file and decide which definition is live.',
            'Use plain-file INSERT with LINE: N to target the exact spot.',
        ],
    },
    'line': {
        'message': 'Plain file INSERT needs LINE: N.',
        'why': 'For non-AST targets, Forge needs an explicit line number to know where to splice the body.',
        'example': [
            'READ docs/example.txt',
            '',
            'INSERT docs/example.txt',
            'LINE: 4',
            'POSITION: after',
            'BEGIN_BODY',
            'new line',
            'END_BODY',
        ],
        'next': [
            'READ the file to get the current line number.',
            'Use POSITION: before or POSITION: after for plain files.',
            'For Python helper functions/classes, prefer AST sibling insertion: INSERT app.py::existing_function with POSITION: after.',
        ],
    },
    'anchor': {
        'message': 'Anchored INSERT could not resolve the anchor safely.',
        'why': 'Forge searches only inside the resolved AST target. The anchor may not match exactly, or it may match more times than EXPECT allows.',
        'example': [
            'READ app.py::main',
            '',
            'INSERT app.py::main',
            'ANCHOR: if ready:',
            'POSITION: after',
            'INDENT: child',
            'BEGIN_BODY',
            'run()',
            'END_BODY',
            '',
            'INSERT app.py::main',
            'ANCHOR: print("same")',
            'POSITION: after',
            'INDENT: same',
            'OCCURRENCE: 2',
            'EXPECT: 2',
            'BEGIN_BODY',
            'run_after_second_match()',
            'END_BODY',
        ],
        'next': [
            'READ the AST target and copy the anchor exactly.',
            'If the anchor matched 0 times, check spelling, indentation, or use MATCH: fuzzy for whitespace drift.',
            'If the anchor matched more than once, make it more specific or use OCCURRENCE with EXPECT deliberately.',
        ],
    },
    'position': {
        'message': 'INSERT POSITION must fit the target shape.',
        'why': 'Plain files support only before/after with LINE. AST body insertion supports start/end. Anchored insertion supports before/after around the anchor.',
        'example': [
            'INSERT docs/example.txt',
            'LINE: 4',
            'POSITION: after',
            'BEGIN_BODY',
            'new line',
            'END_BODY',
            '',
            'INSERT app.py::main',
            'POSITION: end',
            'BEGIN_BODY',
            'print("done")',
            'END_BODY',
        ],
        'next': [
            'Use POSITION: before or POSITION: after for plain files.',
            'Use POSITION: start/end only with AST targets like app.py::main.',
            'Use POSITION: before/after when ANCHOR is present.',
        ],
    },
    'indent': {
        'message': 'INSERT INDENT must be auto, same, or child.',
        'why': 'Indent mode controls how inserted code aligns with the anchor line.',
        'example': [
            'INSERT app.py::main',
            'ANCHOR: if ready:',
            'POSITION: after',
            'INDENT: child',
            'BEGIN_BODY',
            'run()',
            'END_BODY',
        ],
        'next': [
            'Use INDENT: auto unless you deliberately need same or child.',
            'Use INDENT: child when inserting under a block header like if/for/while/try.',
            'Use INDENT: same when inserting beside the anchor line.',
        ],
    },
}

def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _normalise_position(value):
    pos = str(value or '').strip().lower()
    if not pos:
        return 'after'
    aliases = {
        'prepend': 'start',
        'append': 'end',
        'top': 'start',
        'bottom': 'end',
    }
    return aliases.get(pos, pos)


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if not target:
        errors.append('INSERT requires a target')
    if not parsed_op.get('body'):
        errors.append('INSERT requires body content')

    pos = _normalise_position(directives.get('POSITION'))
    has_anchor = 'ANCHOR' in directives
    is_ast = '::' in target
    is_plain_file = not is_ast

    if pos not in ('before', 'after', 'start', 'end'):
        errors.append('INSERT POSITION must be before, after, start, or end')

    if has_anchor and pos not in ('before', 'after'):
        errors.append('INSERT with ANCHOR requires POSITION before or after')

    if is_plain_file and pos not in ('before', 'after'):
        errors.append('Plain file INSERT requires POSITION before or after')

    indent = str(directives.get('INDENT') or 'auto').strip().lower()
    if indent not in ('auto', 'same', 'child'):
        errors.append('INSERT INDENT must be auto, same, or child')

    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    if match_mode not in ('exact', 'fuzzy'):
        errors.append('INSERT MATCH must be exact or fuzzy')

    if 'LINE' in directives:
        line = _as_int(directives.get('LINE'), 0)
        if line < 1:
            errors.append('INSERT LINE must be an integer >= 1')

    if is_plain_file and ('LINE' not in directives):
        errors.append('Plain file INSERT requires LINE: N')

    return errors

def _anchor_index(lines, anchor, match_mode, occurrence, expect):
    needle = str(anchor or '')
    if not needle:
        return None, 'ANCHOR is empty'

    matches = []
    for i, line in enumerate(lines):
        hay = line
        if match_mode == 'fuzzy':
            if needle.strip() in hay.strip():
                matches.append(i)
        else:
            if needle in hay:
                matches.append(i)

    if expect and len(matches) != expect:
        return None, 'ANCHOR matched %d times, expected %d' % (len(matches), expect)

    if occurrence < 1:
        occurrence = 1

    if occurrence > len(matches):
        return None, 'ANCHOR occurrence %d not found; matched %d times' % (
            occurrence,
            len(matches),
        )

    return matches[occurrence - 1], None


def _indent_for(anchor_line, mode):
    base = line_indent(anchor_line)
    if mode == 'child':
        return base + '    '
    if mode == 'same':
        return base
    if anchor_line.rstrip().endswith(':'):
        return base + '    '
    return base


def _execute_plain_file(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    body = parsed_op.get('body') or ''
    directives = parsed_op.get('directives') or {}

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
    total = len(before.splitlines())
    line_no = _as_int(directives.get('LINE'), 0)
    pos = _normalise_position(directives.get('POSITION'))

    if line_no > total:
        result['status'] = 'FAILED_PARSE'
        result['message'] = 'LINE out of range: file has %d lines' % total
        return

    insert_line = line_no - 1 if pos == 'before' else line_no
    inserted_lines = len(str(body).splitlines())

    try:
        after = insert_after_line(before, insert_line, body, indent='', tight=True)
    except Exception as e:
        result['status'] = 'FAILED_PARSE'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    from forge_core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(abs_path, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Insert refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    touched = touched_file(target, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    mode = 'line-%s' % pos

    result['status'] = 'APPLIED'
    result['message'] = 'Inserted into %s %s line %d' % (target, pos, line_no)
    result['file'] = target
    result['preview'] = '\n'.join([
        'INSERT %s' % target,
        'mode: %s' % mode,
        'position: %s' % pos,
        'line: %d' % line_no,
        'inserted: %d line%s' % (inserted_lines, '' if inserted_lines == 1 else 's'),
    ])
    result['data'] = {
        'path': target,
        'file': target,
        'line': line_no,
        'position': pos,
        'mode': mode,
        'inserted_lines': inserted_lines,
    }


def _execute_ast(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    body = parsed_op.get('body') or ''
    directives = parsed_op.get('directives') or {}

    from forge_core.environment import path_from_ctx
    root = path_from_ctx(ctx, 'project_root')
    resolved = resolve_ast_target(root, target)

    if not resolved.get('ok'):
        result['status'] = resolved.get('code') or 'FAILED_NOT_FOUND'
        result['message'] = resolved.get('error') or 'Target not found'
        return

    file_ref = resolved.get('file_ref') or target.split('::', 1)[0]
    file_abs, before, err = read_source(root, file_ref)
    if err:
        result['status'] = 'FAILED_IO'
        result['message'] = err
        return

    all_lines = before.splitlines()
    start = int(resolved.get('start') or 1)
    end = int(resolved.get('end') or start)
    pos = _normalise_position(directives.get('POSITION'))
    inserted_lines = len(str(body).splitlines())

    anchor = str(directives.get('ANCHOR') or '')
    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    occurrence = _as_int(directives.get('OCCURRENCE'), 1)
    expect = _as_int(directives.get('EXPECT'), 1)
    indent_mode = str(directives.get('INDENT') or 'auto').strip().lower()

    mode = 'ast-%s' % pos
    insert_at = None

    try:
        if anchor:
            target_lines = all_lines[start - 1:end]
            rel_idx, anchor_err = _anchor_index(
                target_lines,
                anchor,
                match_mode,
                occurrence,
                expect,
            )
            if anchor_err:
                result['status'] = 'SKIPPED_ANCHOR_MISMATCH'
                result['message'] = 'ANCHOR: ' + anchor_err
                result['data'] = {
                    'target': target,
                    'file': file_ref,
                    'position': pos,
                    'mode': 'anchor-%s' % indent_mode,
                    'anchor': anchor,
                    'match': match_mode,
                    'occurrence': occurrence,
                    'expect': expect,
                    'start': start,
                    'end': end,
                    'kind': resolved.get('kind'),
                    'inserted_lines': 0,
                }
                return

            abs_line = start + rel_idx
            anchor_line = all_lines[abs_line - 1]
            indent = _indent_for(anchor_line, indent_mode)
            insert_line = abs_line - 1 if pos == 'before' else abs_line
            after = insert_after_line(before, insert_line, body, indent=indent, tight=True)
            mode = 'anchor-%s' % indent_mode
            insert_at = abs_line

        elif pos == 'before':
            ref_line = all_lines[start - 1]
            after = insert_after_line(before, start - 1, body, indent=line_indent(ref_line), tight=False)
            mode = 'ast-before'
            insert_at = start

        elif pos == 'after':
            ref_line = all_lines[start - 1]
            after = insert_after_line(before, end, body, indent=line_indent(ref_line), tight=False)
            mode = 'ast-after'
            insert_at = end

        elif pos == 'start':
            ref_line = all_lines[start - 1]
            after = insert_after_line(before, start, body, indent=line_indent(ref_line) + '    ', tight=True)
            mode = 'body-start'
            insert_at = start + 1

        else:
            ref_line = all_lines[start - 1]
            after = insert_after_line(before, max(start, end - 1), body, indent=line_indent(ref_line) + '    ', tight=True)
            mode = 'body-end'
            insert_at = max(start, end - 1)

    except Exception as e:
        result['status'] = 'FAILED_PARSE'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    from forge_core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(file_abs, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Insert refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    touched = touched_file(file_ref, before, after, existed_before=True)
    record_touched(ctx, result, touched)

    preview = [
        'INSERT %s' % target,
        'mode: %s' % mode,
        'position: %s' % pos,
        'target span: %d-%d' % (start, end),
        'inserted: %d line%s' % (inserted_lines, '' if inserted_lines == 1 else 's'),
    ]
    if insert_at is not None:
        preview.append('insert at: %d' % insert_at)
    if anchor:
        preview.extend([
            'anchor: %s' % anchor,
            'indent: %s' % indent_mode,
            'match: %s' % match_mode,
            'occurrence: %d' % occurrence,
            'expect: %d' % expect,
        ])

    result['status'] = 'APPLIED'
    result['message'] = 'Inserted into %s' % target
    result['file'] = file_ref
    result['preview'] = '\n'.join(preview)
    result['data'] = {
        'target': target,
        'file': file_ref,
        'position': pos,
        'mode': mode,
        'start': start,
        'end': end,
        'insert_at': insert_at,
        'kind': resolved.get('kind'),
        'anchor': anchor,
        'indent': indent_mode if anchor else '',
        'match': match_mode if anchor else '',
        'occurrence': occurrence if anchor else '',
        'expect': expect if anchor else '',
        'inserted_lines': inserted_lines,
    }


def execute(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    if '::' in target:
        _execute_ast(ctx, parsed_op, result)
    else:
        _execute_plain_file(ctx, parsed_op, result)
