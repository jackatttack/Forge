# -*- coding: utf-8 -*-
"""
INSERT operation.

Unified insertion operation for files and AST targets.

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

from forge.core.ast_tools import resolve_ast_target, read_source
from forge.core.file_safety import safe_target, read_text, write_text, touched_file, record_touched, split_root_prefix
from forge.core.source_edit import insert_after_line, line_indent


SPEC = {
    'name': 'INSERT',
    'target_kind': 'path',
    'body_mode': 'required',
    'allowed_directives': set([
        'ANCHOR',
        'CONFIRM',
        'EXPECT',
        'IF_VERSION',
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
    'brief': (
        'Plain file: ANCHOR: text (or LINE: N) with POSITION: before|after · '
        'path::Target with POSITION: before|after (sibling) or start|end '
        '(inside) · ANCHOR inside a target, INDENT: child nests · '
        'OCCURRENCE: N picks a repeated anchor · IF_VERSION pins.'
    ),
    'minimal_example': [
        'INSERT docs/notes.md',
        'ANCHOR: ## Setup',
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
        '',
        'INSERT .github/workflows/ci.yml',
        'LINE: 12',
        'POSITION: after',
        'BEGIN_BODY',
        '      - name: Run tests',
        '        run: python -m unittest',
        'END_BODY',
    ],
    'directives': {
        'IF_VERSION': (
            'Refuse the insert unless the file still has this version from '
            'an earlier READ or edit result.'
        ),
        'ANCHOR': (
            'Text on an existing line; the body goes before or after that '
            'line. Searches the whole plain file, or only inside path::Target.'
        ),
        'CONFIRM': (
            'Use yes only to approve an intentional edit when the '
            'shared core guard identifies the target as protected.'
        ),
        'EXPECT': (
            'Assert the total anchor-match count. Without EXPECT or '
            'OCCURRENCE the anchor must match exactly once.'
        ),
        'INDENT': (
            'Anchored AST indentation: auto, same, or child.'
        ),
        'LINE': (
            'One-based line in a plain file, from a fresh READ. Use LINE or '
            'ANCHOR, not both.'
        ),
        'MATCH': (
            'Anchor matching: exact or fuzzy; the default is exact.'
        ),
        'OCCURRENCE': (
            'Select the Nth anchor match; works on its own, like REPLACE.'
        ),
        'POSITION': (
            'before/after for plain files, anchors and AST siblings; '
            'start/end for AST bodies.'
        ),
    },
    'common_failures': [
        'Plain-file insertion with neither ANCHOR nor LINE, or with both.',
        'Using start or end on a plain file.',
        'A repeated anchor without OCCURRENCE.',
        'A stale LINE number after earlier edits in the same bundle.',
        'Producing invalid Python after insertion.',
    ],
    'safe_usage': [
        'READ the exact target or surrounding lines first.',
        'Prefer ANCHOR over LINE: content anchors survive earlier edits.',
        'Use explicit POSITION rather than relying on placement guesses.',
        'Preserve exact body whitespace for plain-file insertion.',
        'Use INDENT only for anchored AST insertion.',
        'Check the landed lines in the result preview.',
    ],
    'related_ops': ['READ', 'REPLACE', 'WRITE'],
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
            'Target the file without :: and place the body with ANCHOR: text or LINE: N.',
        ],
    },
    'line': {
        'message': 'Plain file INSERT needs ANCHOR: text or LINE: N, not both.',
        'why': 'Forge needs to know which line to insert beside. ANCHOR finds it by content, so it survives earlier edits; LINE needs a current line number.',
        'example': [
            'INSERT docs/example.txt',
            'ANCHOR: ## Setup',
            'POSITION: after',
            'BEGIN_BODY',
            'new line',
            'END_BODY',
        ],
        'next': [
            'Prefer ANCHOR with text from a line you have already seen.',
            'Use LINE: N only with a line number from a fresh READ.',
            'Use POSITION: before or POSITION: after for plain files.',
            'For Python helper functions/classes, prefer AST sibling insertion: INSERT app.py::existing_function with POSITION: after.',
        ],
    },
    'anchor': {
        'message': 'Anchored INSERT could not resolve the anchor safely.',
        'why': 'In a plain file Forge searches the whole file; with path::Target only inside that target. Without OCCURRENCE or EXPECT the anchor must match exactly once, so a repeated anchor is refused rather than guessed.',
        'example': [
            'INSERT app.py::main',
            'ANCHOR: if ready:',
            'POSITION: after',
            'INDENT: child',
            'BEGIN_BODY',
            'run()',
            'END_BODY',
            '',
            'INSERT notes.txt',
            'ANCHOR: same line text',
            'POSITION: after',
            'OCCURRENCE: 2',
            'BEGIN_BODY',
            'inserted after the second match',
            'END_BODY',
        ],
        'next': [
            'Copy the anchor exactly from a line you have READ.',
            'If it matched 0 times, check spelling or use MATCH: fuzzy for whitespace drift.',
            'If it matched more than once, make it more specific or add OCCURRENCE: N.',
            'Add EXPECT: N only when you also want the total number of matches asserted.',
        ],
    },
    'position': {
        'message': 'INSERT POSITION must fit the target shape.',
        'why': 'Plain files and anchors support before/after. AST sibling insertion supports before/after the target. AST body insertion supports start/end.',
        'example': [
            'INSERT docs/example.txt',
            'ANCHOR: ## Setup',
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
    """
    Static rules for INSERT, checked before any op in the bundle runs.

    Only the parsed op is available here, never the file. Checks that
    depend on file contents (LINE past the end, anchor matches) belong in
    execute().
    """
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if not target:
        errors.append('INSERT requires a target')
    if not parsed_op.get('body'):
        errors.append('INSERT requires body content')

    pos = _normalise_position(directives.get('POSITION'))
    has_anchor = 'ANCHOR' in directives
    has_line = 'LINE' in directives
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

    if has_line and _as_int(directives.get('LINE'), 0) < 1:
        errors.append('INSERT LINE must be an integer >= 1')

    if 'OCCURRENCE' in directives and _as_int(directives.get('OCCURRENCE'), 0) < 1:
        errors.append('INSERT OCCURRENCE must be an integer >= 1')

    if 'EXPECT' in directives and _as_int(directives.get('EXPECT'), 0) < 1:
        errors.append('INSERT EXPECT must be an integer >= 1')

    if has_line and has_anchor:
        errors.append('INSERT takes LINE or ANCHOR, not both')

    if is_plain_file and not has_line and not has_anchor:
        errors.append('Plain file INSERT requires LINE: N or ANCHOR: text')

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

def _anchor_selection(directives):
    """
    Return (occurrence, expect) for anchored insertion.

    With neither directive the anchor must match exactly once, so an
    ambiguous anchor is refused rather than guessed. OCCURRENCE alone picks
    the Nth match without asserting the total, the same as REPLACE. EXPECT,
    when given, always asserts the total. expect 0 means "not asserted".
    """
    occurrence = _as_int(directives.get('OCCURRENCE'), 1)
    if 'EXPECT' in directives:
        expect = _as_int(directives.get('EXPECT'), 1)
    elif 'OCCURRENCE' in directives:
        expect = 0
    else:
        expect = 1
    return occurrence, expect


def _landed_region(before, after):
    """
    Return the first and last line (1-based) of `after` that differ from
    `before`. Comparing whole texts reports where the body really landed,
    whatever blank-line handling insert_after_line applied.
    """
    old = before.splitlines()
    new = after.splitlines()
    limit = min(len(old), len(new))
    prefix = 0
    while prefix < limit and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < limit - prefix and old[len(old) - 1 - suffix] == new[len(new) - 1 - suffix]:
        suffix += 1
    first = prefix + 1
    last = max(first, len(new) - suffix)
    return first, last


def _landed_context(after, first, last, context=2, max_shown=12):
    """
    Numbered lines around an insertion, inserted lines marked with '>'.

    Lets the packet confirm placement without another READ. Long insertions
    show only their first and last few lines.
    """
    lines = after.splitlines()
    low = max(1, first - context)
    high = min(len(lines), last + context)
    numbers = list(range(low, high + 1))
    if last - first + 1 > max_shown:
        half = max_shown // 2
        numbers = [n for n in numbers if n < first + half or n > last - half]
    out = []
    previous = None
    for n in numbers:
        if previous is not None and n != previous + 1:
            out.append('  ....')
        marker = '>' if first <= n <= last else ' '
        out.append('%s %04d: %s' % (marker, n, lines[n - 1]))
        previous = n
    return out


def _execute_plain_file(ctx, parsed_op, result):
    """
    Insert verbatim text into a non-Python target.

    Placement comes from LINE (an inspected line number) or ANCHOR (a line
    containing the anchor text, selected by OCCURRENCE and checked by
    EXPECT). validate() guarantees exactly one of the two is present.
    """
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
    lines = before.splitlines()
    pos = _normalise_position(directives.get('POSITION'))
    anchor = str(directives.get('ANCHOR') or '')
    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    occurrence, expect = _anchor_selection(directives)

    if anchor:
        index, anchor_err = _anchor_index(lines, anchor, match_mode, occurrence, expect)
        if anchor_err:
            result['status'] = 'SKIPPED_ANCHOR_MISMATCH'
            result['message'] = 'ANCHOR: ' + anchor_err
            result['data'] = {
                'path': target,
                'file': target,
                'anchor': anchor,
                'match': match_mode,
                'occurrence': occurrence,
                'expect': expect,
                'inserted_lines': 0,
            }
            return
        line_no = index + 1
    else:
        line_no = _as_int(directives.get('LINE'), 0)
        if line_no > len(lines):
            # The bundle was well formed; the file is shorter than expected.
            result['status'] = 'FAILED_NOT_FOUND'
            result['message'] = 'LINE %d out of range: file has %d lines' % (line_no, len(lines))
            return

    insert_line = line_no - 1 if pos == 'before' else line_no
    inserted_lines = len(str(body).splitlines())

    try:
        # Plain files get the body verbatim. See insert_after_line.
        after = insert_after_line(
            before,
            insert_line,
            body,
            indent='',
            tight=True,
            dedent=False,
        )
    except Exception as e:
        result['status'] = 'FAILED_RUNTIME'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    from forge.core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(abs_path, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Insert refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    target_root, target_rel = split_root_prefix(target)
    touched = touched_file(
        target_rel, before, after, existed_before=True,
        root=target_root or '',
    )
    record_touched(ctx, result, touched)

    mode = ('anchor-%s' if anchor else 'line-%s') % pos
    landed_start, landed_end = _landed_region(before, after)

    preview_lines = [
        'INSERT %s' % target,
        'mode: %s' % mode,
        'position: %s' % pos,
    ]
    if anchor:
        preview_lines.extend([
            'anchor: %s' % anchor,
            'anchor line: %d' % line_no,
            'occurrence: %d' % occurrence,
            'expect: %s' % (expect or 'not asserted'),
        ])
    else:
        preview_lines.append('line: %d' % line_no)
    preview_lines.append(
        'inserted: %d line%s' % (inserted_lines, '' if inserted_lines == 1 else 's'))
    preview_lines.append('landed: lines %d-%d' % (landed_start, landed_end))
    preview_lines.extend(_landed_context(after, landed_start, landed_end))

    result['status'] = 'APPLIED'
    result['message'] = 'Inserted into %s %s line %d' % (target, pos, line_no)
    result['file'] = target
    result['preview'] = '\n'.join(preview_lines)
    result['data'] = {
        'path': target,
        'file': target,
        'line': line_no,
        'position': pos,
        'mode': mode,
        'anchor': anchor,
        'inserted_lines': inserted_lines,
        'landed_start': landed_start,
        'landed_end': landed_end,
    }


def _starts_with_definition(body):
    """
    True when the inserted code opens with def, async def, class or a
    decorator.

    Body-end insertion is tight (no added blank lines) so a statement sits
    right after the last line. A new method or nested class wants Python
    spacing instead, so it gets the same blank-line handling as AST after.
    """
    for line in str(body or '').splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.startswith(('def ', 'async def ', 'class ', '@'))
    return False


def _execute_ast(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    body = parsed_op.get('body') or ''
    directives = parsed_op.get('directives') or {}

    # Resolve any "name:" root prefix first, exactly as REPLACE does, so an
    # AST target on a configured root reads and writes that root's file.
    # file_target keeps the prefix; it is what the touched record needs.
    file_target, _separator, ast_target = target.partition('::')
    root, file_abs, err = safe_target(ctx, file_target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    try:
        file_ref = os.path.relpath(file_abs, root)
    except Exception:
        file_ref = split_root_prefix(file_target)[1]

    resolved = resolve_ast_target(root, file_ref + '::' + ast_target)

    if not resolved.get('ok'):
        result['status'] = resolved.get('code') or 'FAILED_NOT_FOUND'
        result['message'] = resolved.get('error') or 'Target not found'
        return

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
    occurrence, expect = _anchor_selection(directives)
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
            # end is the target's last line (inclusive), so insert after it.
            # end - 1 landed before the last line and split a class's final
            # method in two.
            after = insert_after_line(
                before, end, body,
                indent=line_indent(ref_line) + '    ',
                tight=not _starts_with_definition(body),
            )
            mode = 'body-end'
            insert_at = end + 1

    except Exception as e:
        result['status'] = 'FAILED_RUNTIME'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    from forge.core.file_safety import checked_write, CompileBlocked

    try:
        checked_write(file_abs, after)
    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'Insert refused: result would not compile. Line %s: %s. '
            'File untouched.' % (e.lineno, e.msg)
        )
        return
    file_root, file_rel = split_root_prefix(file_target)
    touched = touched_file(
        file_rel, before, after, existed_before=True,
        root=file_root or '',
    )
    record_touched(ctx, result, touched)

    # Count what actually landed. The body's edge blank lines are trimmed
    # and Python spacing may be added, so the body's own length misleads.
    landed_start, landed_end = _landed_region(before, after)
    inserted_lines = max(0, landed_end - landed_start + 1)

    preview = [
        'INSERT %s' % target,
        'mode: %s' % mode,
        'position: %s' % pos,
        'target span: %d-%d' % (start, end),
        'inserted: %d line%s' % (inserted_lines, '' if inserted_lines == 1 else 's'),
    ]

    if anchor:
        preview.extend([
            'anchor: %s' % anchor,
            'indent: %s' % indent_mode,
            'match: %s' % match_mode,
            'occurrence: %d' % occurrence,
            'expect: %s' % (expect or 'not asserted'),
        ])

    preview.append('landed: lines %d-%d' % (landed_start, landed_end))
    preview.extend(_landed_context(after, landed_start, landed_end))

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
