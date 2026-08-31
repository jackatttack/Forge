# -*- coding: utf-8 -*-
"""
READ reboot op.

Public read-only inspection verb for Forge.

READ is the normal source/content inspection step before INSERT, REPLACE,
DELETE, and RUN.

Directory structure belongs to MAP. Python target discovery is available through
TARGETS: yes or through MAP MODE: targets.
"""

import os


SPEC = {
    'name': 'READ',
    'target_kind': 'path',
    'body_mode': 'forbidden',
    'allowed_directives': set(['LINES', 'ANCHOR', 'CONTEXT', 'MATCH', 'TARGETS', 'DOCS']),
    'required_directives': set(),
}

HELP = {
    'summary': 'Read a file, directory, AST target, anchored slice, or Python target list.',
    'minimal_example': [
        'READ app.py',
        '',
        'READ app.py',
        'LINES: 1-80',
        '',
        'READ app.py::main',
        '',
        'READ app.py',
        'TARGETS: yes',
        '',
        'READ app.py',
        'ANCHOR: def main',
        'CONTEXT: 8',
        '',
        'READ app.py',
        'ANCHOR: if ready:',
        'MATCH: fuzzy',
        'CONTEXT: 6',
        '',
        'READ docs',
        'DEPTH: 3',
        'FILES: yes',
    ],
}


HINTS = {
    '_max_hints': 1,

    'file not found': {
        'message': 'READ could not find the requested file.',
        'why': 'The path must exist inside project_root.',
        'example': [
            'MAP .',
            '',
            'READ path/to/file.py',
        ],
        'next': [
            'Use MAP on the containing directory to locate the current path.',
            'Use SEARCH when you know text or a symbol from the file but not its location.',
        ],
    },

    'target': {
        'message': 'READ needs a file path or AST target.',
        'why': 'READ is the inspect-first step before editing.',
        'example': [
            'READ forge/smoke.py',
            'LINES: 1-80',
            '',
            'READ forge/smoke.py::main',
            '',
            'READ forge/smoke.py',
            'TARGETS: yes',
        ],
        'next': [
            'Use MAP or SEARCH to locate paths.',
            'Use READ with TARGETS: yes or MAP MODE: targets to discover Python AST targets.',
        ],
    },
}


def validate(parsed_op):
    if not (parsed_op.get('target') or '').strip():
        return ['READ requires a target path or AST target']
    return []


def _in_root(root, path):
    root_real = os.path.realpath(os.path.abspath(root))
    path_real = os.path.realpath(os.path.abspath(path))
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _as_bool(value):
    return str(value or '').strip().lower() in ('1', 'yes', 'y', 'true', 'on')


def _parse_lines(raw, total, default_limit):
    text = str(raw or '').strip()

    if not text:
        return 1, total

    if '-' in text:
        left, _sep, right = text.partition('-')
        try:
            start = int(left.strip())
            end = int(right.strip())
        except Exception:
            start = 1
            end = min(total, default_limit)
    else:
        try:
            start = int(text)
            end = start
        except Exception:
            start = 1
            end = min(total, default_limit)

    if start < 1:
        start = 1
    if end < start:
        end = start
    if end > total:
        end = total

    return start, end


def _normalise_for_match(text):
    return ' '.join(str(text or '').strip().split())


def _anchor_range(lines, anchor, context, match_mode):
    anchor = str(anchor or '')
    if not anchor:
        return None

    fuzzy = str(match_mode or '').strip().lower() == 'fuzzy'
    wanted = _normalise_for_match(anchor) if fuzzy else anchor

    matches = []
    for idx, line in enumerate(lines):
        hay = _normalise_for_match(line) if fuzzy else line
        if wanted in hay:
            matches.append(idx + 1)

    if not matches:
        return None

    line_no = matches[0]
    start = max(1, line_no - context)
    end = min(len(lines), line_no + context)
    return start, end


def _format_read(title, lines, start, end):
    selected = lines[start - 1:end]
    width = max(4, len(str(end)))

    out = []
    out.append('%s [lines %d-%d of %d]' % (title, start, end, len(lines)))

    for offset, line in enumerate(selected):
        n = start + offset
        out.append(('%0' + str(width) + 'd: %s') % (n, line))

    return out


def _read_file(root, target, directives):
    abs_path = os.path.abspath(os.path.join(root, target))

    if not _in_root(root, abs_path):
        return None, 'FAILED_IO', 'Path escapes project root'

    if not os.path.isfile(abs_path):
        return None, 'FAILED_NOT_FOUND', 'File not found: ' + target

    try:
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
    except Exception as e:
        return None, 'FAILED_IO', 'Could not read file: %s: %s' % (type(e).__name__, e)

    lines = src.splitlines()
    total = len(lines)
    default_limit = 120

    if directives.get('ANCHOR'):
        context = _as_int(directives.get('CONTEXT'), 10)
        found = _anchor_range(lines, directives.get('ANCHOR'), context, directives.get('MATCH'))
        if not found:
            return None, 'FAILED_NOT_FOUND', 'ANCHOR matched 0 times'
        start, end = found
    else:
        start, end = _parse_lines(directives.get('LINES'), total, default_limit)

    return {
        'mode': 'file',
        'title': 'READ ' + target,
        'path': target,
        'start': start,
        'end': end,
        'total': total,
        'lines': lines[start - 1:end],
        'preview_lines': _format_read(target, lines, start, end),
    }, None, None


def _read_directory(ctx, target, directives):
    """Reject directory targets cleanly; MAP owns structural inspection."""
    return (
        None,
        'FAILED_INVALID_PATH',
        'READ targets files or Python targets. Use MAP for directories: MAP %s'
        % (
            target
            or '.'
        ),
    )


def _read_ast(root, target, directives):
    try:
        from forge_core.ast_tools import resolve_ast_target
    except Exception as e:
        return None, 'FAILED_RUNTIME', 'AST tools unavailable: %s: %s' % (type(e).__name__, e)

    resolved = resolve_ast_target(root, target)
    if not resolved.get('ok'):
        return None, 'FAILED_NOT_FOUND', resolved.get('error') or 'AST target not found'

    src = resolved.get('source_text') or ''
    lines = src.splitlines()
    start = int(resolved.get('start') or 1)
    end = int(resolved.get('end') or start)

    file_ref = resolved.get('file_ref') or target

    return {
        'mode': 'ast',
        'title': 'READ ' + target,
        'path': file_ref,
        'ast_target': target,
        'kind': resolved.get('kind') or '',
        'start': start,
        'end': end,
        'total': len(lines),
        'lines': lines[start - 1:end],
        'preview_lines': _format_read(target, lines, start, end),
    }, None, None


def _read_targets(root, target, directives):
    try:
        from forge_core.ast_tools import list_targets
    except Exception as e:
        return None, 'FAILED_RUNTIME', 'AST tools unavailable: %s: %s' % (type(e).__name__, e)

    docs_mode = str(directives.get('DOCS') or 'yes').strip().lower() or 'yes'
    rows, err = list_targets(root, target, docs_mode=docs_mode)
    if err:
        if 'not found' in err.lower():
            return None, 'FAILED_NOT_FOUND', err
        if 'escapes' in err.lower():
            return None, 'FAILED_IO', err
        return None, 'FAILED_PARSE', err

    lines = []
    lines.append('READ %s [targets %d]' % (target, len(rows or [])))

    for row in rows or []:
        pad = '  ' * int(row.get('indent') or 0)
        line = '%-58s %s' % (pad + row.get('target', ''), row.get('range') or '')
        if docs_mode != 'no':
            doc = row.get('doc') or '∅'
            line += '  # ' + doc[:80]
        lines.append(line.rstrip())

    return {
        'mode': 'targets',
        'path': target,
        'targets': rows or [],
        'preview_lines': lines,
    }, None, None


def execute(ctx, parsed_op, result):
    from forge_core.environment import path_from_ctx
    root = path_from_ctx(ctx, 'project_root')
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    abs_target = os.path.abspath(os.path.join(root, target))

    if _as_bool(directives.get('TARGETS')):
        data, status, message = _read_targets(root, target, directives)
    elif '::' in target:
        data, status, message = _read_ast(root, target, directives)
    elif os.path.isdir(abs_target):
        data, status, message = _read_directory(ctx, target, directives)
    else:
        data, status, message = _read_file(root, target, directives)

    if status:
        result['status'] = status
        result['message'] = message
        return

    result['status'] = 'APPLIED'
    mode = data.get('mode') or 'file'
    if mode == 'targets':
        result['message'] = '%d targets' % len(data.get('targets') or [])
    elif mode == 'directory':
        result['message'] = 'Directory: ' + (data.get('path') or target)
    else:
        result['message'] = 'Lines %d-%d' % (data.get('start'), data.get('end'))

    result['preview'] = '\n'.join(data.get('preview_lines') or []).rstrip()
    result['file'] = data.get('path') or target
    result['data'] = data
