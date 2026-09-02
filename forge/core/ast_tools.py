# -*- coding: utf-8 -*-
"""
AST helpers for the Forge.

This is intentionally close to Forge2's proven target model:
    file.py::function
    file.py::Class.method
    file.py::Class.*
    file.py::@ASSIGNMENT
    file.py::Class.@ASSIGNMENT

The goal is not cleverness. The goal is stable target discovery and exact
line ranges before any AST write op is allowed to exist.
"""

import ast
import os


def in_root(root, path):
    root_real = os.path.realpath(os.path.abspath(root))
    path_real = os.path.realpath(os.path.abspath(path))
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def resolve_file(project_root, file_ref):
    file_ref = str(file_ref or '').strip()
    if os.path.isabs(file_ref):
        return os.path.abspath(file_ref)
    return os.path.abspath(os.path.join(project_root, file_ref))


def parse_target_ref(target_ref, default_file=None):
    raw = str(target_ref or '').strip()
    if '::' in raw:
        file_ref, rhs = raw.split('::', 1)
    else:
        file_ref, rhs = default_file, raw

    file_ref = str(file_ref or '').strip()
    rhs = str(rhs or '').strip()

    if not file_ref:
        return None

    class_name = None
    target_name = rhs

    if '.' in rhs:
        lhs, tail = rhs.split('.', 1)
        if tail:
            class_name = lhs.strip()
            target_name = tail.strip()

    return {
        'file_ref': file_ref,
        'class_name': class_name,
        'target_name': target_name,
    }


def read_source(project_root, file_ref):
    file_abs = resolve_file(project_root, file_ref)
    if not in_root(project_root, file_abs):
        return None, None, 'Target escapes project root'
    if not os.path.isfile(file_abs):
        return None, None, 'File not found: ' + str(file_ref)
    try:
        with open(file_abs, 'r', encoding='utf-8', errors='replace') as f:
            return file_abs, f.read(), None
    except Exception as e:
        return file_abs, None, 'Could not read file: %s: %s' % (type(e).__name__, e)


def end_lineno(node):
    value = getattr(node, 'end_lineno', None)
    if value:
        return value

    best = getattr(node, 'lineno', 1)
    for child in ast.walk(node):
        n = getattr(child, 'lineno', None)
        if n and n > best:
            best = n
    return best


def range_text(node):
    start = getattr(node, 'lineno', 1)
    end = end_lineno(node)
    if start == end:
        return '[%d]' % start
    return '[%d-%d]' % (start, end)


def first_doc(node):
    try:
        raw = ast.get_docstring(node) or ''
        for line in raw.splitlines():
            line = line.strip()
            if line:
                return line
    except Exception:
        pass
    return ''


def preceding_comment(src_lines, node):
    lineno = getattr(node, 'lineno', 1) - 2
    if 0 <= lineno < len(src_lines):
        text = src_lines[lineno].strip()
        if text.startswith('#'):
            return text.lstrip('#').strip()
    return ''


def assignment_names(node):
    names = []
    if isinstance(node, ast.Assign):
        targets = node.targets or []
    elif isinstance(node, ast.AnnAssign):
        targets = [getattr(node, 'target', None)]
    else:
        targets = []

    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
    return names


def list_targets(project_root, file_ref, docs_mode='yes'):
    file_abs, src, err = read_source(project_root, file_ref)
    if err:
        return None, err

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return None, 'SyntaxError: %s' % e

    try:
        rel = os.path.relpath(file_abs, project_root)
    except Exception:
        rel = file_ref

    src_lines = src.splitlines()
    rows = []

    def add(target, node, doc='', indent=0):
        rows.append({
            'target': target,
            'start': getattr(node, 'lineno', 1),
            'end': end_lineno(node),
            'range': range_text(node),
            'doc': doc or '',
            'indent': indent,
        })

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_target = '%s::%s.*' % (rel, node.name)
            add(class_target, node, first_doc(node), indent=0)

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add('%s::%s.%s' % (rel, node.name, item.name), item, first_doc(item), indent=1)
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    for name in assignment_names(item):
                        add('%s::%s.@%s' % (rel, node.name, name), item, preceding_comment(src_lines, item), indent=1)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add('%s::%s' % (rel, node.name), node, first_doc(node), indent=0)

        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in assignment_names(node):
                add('%s::@%s' % (rel, name), node, preceding_comment(src_lines, node), indent=0)

    return rows, None


def resolve_ast_target(project_root, target_ref, default_file=None):
    parsed = parse_target_ref(target_ref, default_file=default_file)
    if not parsed:
        return {
            'ok': False,
            'error': 'Invalid AST target: ' + str(target_ref),
        }

    file_ref = parsed.get('file_ref')
    file_abs, src, err = read_source(project_root, file_ref)
    if err:
        return {
            'ok': False,
            'error': err,
        }

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {
            'ok': False,
            'error': 'SyntaxError: %s' % e,
        }

    class_name = parsed.get('class_name')
    target_name = parsed.get('target_name')

    def found(node, kind):
        return {
            'ok': True,
            'file_abs': file_abs,
            'file_ref': file_ref,
            'class_name': class_name,
            'target_name': target_name,
            'kind': kind,
            'start': getattr(node, 'lineno', 1),
            'end': end_lineno(node),
            'source_text': src,
        }

    def ambiguous(kind, matches):
        lines = ', '.join(str(getattr(n, 'lineno', '?')) for n in matches)
        return {
            'ok': False,
            'code': 'FAILED_AMBIGUOUS',
            'error': (
                'Ambiguous target: %s matched %d %ss (lines %s). '
                'Disambiguate the source or target a unique name.'
                % (str(target_ref), len(matches), kind, lines)
            ),
        }

    def single(matches, kind, not_found_msg):
        if not matches:
            return {'ok': False, 'error': not_found_msg}
        if len(matches) > 1:
            return ambiguous(kind, matches)
        return found(matches[0], kind)

    if class_name:
        classes = [
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
        if not classes:
            return {'ok': False, 'error': 'Class not found: ' + str(class_name)}
        if len(classes) > 1:
            return ambiguous('class', classes)

        wanted_class = classes[0]

        if target_name == '*':
            return found(wanted_class, 'class')

        if target_name.startswith('@'):
            wanted = target_name[1:]
            matches = [
                item for item in wanted_class.body
                if isinstance(item, (ast.Assign, ast.AnnAssign))
                and wanted in assignment_names(item)
            ]
            return single(
                matches, 'assignment',
                'Class assignment not found: ' + str(target_ref),
            )

        matches = [
            item for item in wanted_class.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == target_name
        ]
        return single(
            matches, 'method',
            'Class target not found: ' + str(target_ref),
        )

    if target_name.startswith('@'):
        wanted = target_name[1:]
        matches = [
            node for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and wanted in assignment_names(node)
        ]
        return single(
            matches, 'assignment',
            'Assignment not found: ' + str(target_ref),
        )

    matches = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == target_name
    ]
    return single(
        matches, 'function',
        'Target not found: ' + str(target_ref),
    )
