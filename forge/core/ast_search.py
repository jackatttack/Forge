# -*- coding: utf-8 -*-
"""
AST-powered structural search helpers for Forge.

This module supports SEARCH MATCH: ast. It is deliberately a locator, not a
dependency graph engine.
"""

import ast
import os


def _end_lineno(node):
    value = getattr(node, 'end_lineno', None)
    if value:
        return value

    best = getattr(node, 'lineno', 1)
    for child in ast.walk(node):
        n = getattr(child, 'lineno', None)
        if n and n > best:
            best = n
    return best


def _call_name(node):
    func = getattr(node, 'func', None)

    if isinstance(func, ast.Name):
        return func.id

    if isinstance(func, ast.Attribute):
        parts = []
        cur = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        parts.reverse()
        return '.'.join(parts)

    return ''


def _import_names(node):
    names = []

    if isinstance(node, ast.Import):
        for alias in node.names or []:
            if alias.name:
                names.append(alias.name)

    elif isinstance(node, ast.ImportFrom):
        module = node.module or ''
        if getattr(node, 'level', 0):
            module = ('.' * int(node.level)) + module
        if module:
            names.append(module)
        for alias in node.names or []:
            if module and alias.name:
                names.append(module + '.' + alias.name)
            elif alias.name:
                names.append(alias.name)

    return names


def _assignment_names(node):
    names = []

    if isinstance(node, ast.Assign):
        targets = node.targets or []
    elif isinstance(node, ast.AnnAssign):
        targets = [getattr(node, 'target', None)]
    else:
        targets = []

    def collect(target):
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            parts = []
            cur = target
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            parts.reverse()
            names.append('.'.join(parts))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts or []:
                collect(item)

    for target in targets:
        collect(target)

    return names


def _contains_name(candidate, wanted, case_sensitive=False):
    candidate = str(candidate or '')
    wanted = str(wanted or '').strip()
    if not wanted:
        return True

    if case_sensitive:
        return candidate == wanted or candidate.endswith('.' + wanted)

    c = candidate.lower()
    w = wanted.lower()
    return c == w or c.endswith('.' + w)


def _scope_target(rel, stack):
    if not stack:
        return rel

    for item in reversed(stack):
        kind, name = item
        if kind == 'function':
            return '%s::%s' % (rel, name)
        if kind == 'method':
            class_name, method_name = name.split('.', 1)
            return '%s::%s.%s' % (rel, class_name, method_name)
        if kind == 'class':
            return '%s::%s.*' % (rel, name)

    return rel


def _source_line(src_lines, node):
    lineno = getattr(node, 'lineno', 1)
    if 1 <= lineno <= len(src_lines):
        return src_lines[lineno - 1].strip()
    return ''


def _hit(rel, node, kind, name, text, target):
    return {
        'file': rel,
        'line': getattr(node, 'lineno', 1),
        'end': _end_lineno(node),
        'kind': kind,
        'name': name,
        'text': text,
        'target': target,
    }


def search_python_source(rel, source_text, criteria):
    criteria = criteria or {}
    defines = str(criteria.get('defines') or '').strip()
    calls = str(criteria.get('calls') or '').strip()
    imports = str(criteria.get('imports') or '').strip()
    assigns = str(criteria.get('assigns') or '').strip()
    case_sensitive = bool(criteria.get('case_sensitive'))

    try:
        tree = ast.parse(source_text or '')
    except SyntaxError as e:
        return [], 'SyntaxError: %s' % e

    src_lines = (source_text or '').splitlines()
    hits = []
    stack = []

    def want(kind):
        if kind == 'define':
            return bool(defines)
        if kind == 'call':
            return bool(calls)
        if kind == 'import':
            return bool(imports)
        if kind == 'assign':
            return bool(assigns)
        return False

    def visit(node):
        if isinstance(node, ast.ClassDef):
            if want('define') and _contains_name(node.name, defines, case_sensitive):
                hits.append(_hit(rel, node, 'class', node.name, _source_line(src_lines, node), '%s::%s.*' % (rel, node.name)))

            stack.append(('class', node.name))
            for child in node.body:
                visit(child)
            stack.pop()
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            in_class = stack and stack[-1][0] == 'class'
            if in_class:
                scope_name = stack[-1][1] + '.' + node.name
                target = '%s::%s' % (rel, scope_name)
                kind = 'method'
                stack_name = scope_name
            else:
                target = '%s::%s' % (rel, node.name)
                kind = 'function'
                stack_name = node.name

            if want('define') and _contains_name(node.name, defines, case_sensitive):
                hits.append(_hit(rel, node, kind, node.name, _source_line(src_lines, node), target))

            stack.append(('method' if in_class else 'function', stack_name))
            for child in node.body:
                visit(child)
            stack.pop()
            return

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if want('import'):
                for name in _import_names(node):
                    if _contains_name(name, imports, case_sensitive):
                        hits.append(_hit(rel, node, 'import', name, _source_line(src_lines, node), _scope_target(rel, stack)))
                        break

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if want('assign'):
                for name in _assignment_names(node):
                    if _contains_name(name, assigns, case_sensitive):
                        hits.append(_hit(rel, node, 'assignment', name, _source_line(src_lines, node), _scope_target(rel, stack)))
                        break

        if isinstance(node, ast.Call):
            if want('call'):
                name = _call_name(node)
                if _contains_name(name, calls, case_sensitive):
                    hits.append(_hit(rel, node, 'call', name, _source_line(src_lines, node), _scope_target(rel, stack)))

        for child in ast.iter_child_nodes(node):
            visit(child)

    for child in tree.body:
        visit(child)

    return hits, None


def search_ast_files(root, files, criteria, limit=80):
    all_hits = []
    searched = 0
    syntax_errors = []

    for path in files:
        searched += 1
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        except Exception:
            continue

        try:
            rel = os.path.relpath(path, root)
        except Exception:
            rel = path

        hits, err = search_python_source(rel, text, criteria)
        if err:
            syntax_errors.append({'file': rel, 'error': err})
            continue

        for hit in hits:
            all_hits.append(hit)
            if len(all_hits) >= limit:
                return all_hits, searched, syntax_errors, True

    return all_hits, searched, syntax_errors, False