# -*- coding: utf-8 -*-
"""
Static project relationship index for Forge.

V1 is deliberately read-only and conservative:
- discover Python files under a requested scope
- record definitions
- resolve local imports where practical
- record calls with their containing Forge-style symbol target
- expose reverse imports and simple caller queries

This module is infrastructure. It does not mutate source files and is not
imported by MAP until its behaviour has been proven independently.
"""

import ast
import os

from forge_core.ast_tools import end_lineno


_SKIP_DIRS = set([
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    'site-packages',
    'site-packages-2',
    'site-packages-3',
    'node_modules',
    'artifacts',
    'snapshots',
    'patch_runs',
    'script_snapshots',
    'build',
    'dist',
])


def _rel(root, path):
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path


def _python_files(root, scope):
    scope_abs = os.path.abspath(scope)

    if os.path.isfile(scope_abs):
        return [scope_abs] if scope_abs.endswith('.py') else []

    rows = []

    for current, dirs, files in os.walk(scope_abs):
        dirs[:] = [
            name for name in dirs
            if name not in _SKIP_DIRS and not name.startswith('.')
        ]

        for name in files:
            if name.endswith('.py'):
                rows.append(os.path.join(current, name))

    rows.sort(key=lambda path: _rel(root, path))
    return rows


def _module_candidates(root, file_abs, module_name, level=0):
    module_name = str(module_name or '').strip('.')
    current_dir = os.path.dirname(file_abs)
    bases = []

    if level:
        base = current_dir

        for _ in range(max(0, int(level) - 1)):
            base = os.path.dirname(base)

        bases.append(base)
    else:
        bases.append(root)

        cursor = current_dir
        root_abs = os.path.abspath(root)
        seen = set()

        while cursor and cursor not in seen:
            seen.add(cursor)
            bases.append(cursor)

            if cursor == root_abs:
                break

            parent = os.path.dirname(cursor)

            if parent == cursor:
                break

            cursor = parent

    parts = [part for part in module_name.split('.') if part]
    candidates = []

    for base in bases:
        if parts:
            candidates.append(os.path.join(base, *parts) + '.py')
            candidates.append(
                os.path.join(base, *(parts + ['__init__.py']))
            )
        else:
            candidates.append(os.path.join(base, '__init__.py'))

    return candidates


def _resolve_module(root, file_abs, module_name, level=0):
    for candidate in _module_candidates(
        root,
        file_abs,
        module_name,
        level=level,
    ):
        if os.path.isfile(candidate):
            return _rel(root, candidate)

    return ''


def _call_name(node):
    func = getattr(node, 'func', None)

    if isinstance(func, ast.Name):
        return func.id

    if isinstance(func, ast.Attribute):
        parts = []
        current = func

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        parts.reverse()
        return '.'.join(parts)

    return ''


def _scope_target(rel, stack):
    if not stack:
        return rel

    kind, name = stack[-1]

    if kind == 'class':
        return '%s::%s.*' % (rel, name)

    return '%s::%s' % (rel, name)


def _definition_target(rel, stack, name, kind):
    if kind == 'class':
        return '%s::%s.*' % (rel, name)

    if stack and stack[-1][0] == 'class':
        return '%s::%s.%s' % (rel, stack[-1][1], name)

    return '%s::%s' % (rel, name)


def _parse_file(root, file_abs):
    rel = _rel(root, file_abs)

    try:
        with open(file_abs, 'r', encoding='utf-8') as handle:
            source = handle.read()
    except Exception as exc:
        return {
            'path': rel,
            'error': '%s: %s' % (type(exc).__name__, exc),
            'definitions': [],
            'imports': [],
            'calls': [],
        }

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            'path': rel,
            'error': 'SyntaxError: %s' % exc,
            'definitions': [],
            'imports': [],
            'calls': [],
        }

    definitions = []
    imports = []
    calls = []
    stack = []

    def add_definition(node, name, kind):
        target = _definition_target(rel, stack, name, kind)

        definitions.append({
            'name': name,
            'kind': kind,
            'target': target,
            'path': rel,
            'line': int(getattr(node, 'lineno', 1)),
            'end': int(end_lineno(node)),
        })

        return target

    def visit(node):
        if isinstance(node, ast.ClassDef):
            # V1 exposes module classes, but does not pretend a class nested
            # inside a function is a normal Forge-addressable top-level class.
            if stack and stack[-1][0] in (
                'function',
                'method',
                'nested',
            ):
                for child in node.body:
                    visit(child)
                return

            add_definition(node, node.name, 'class')
            stack.append(('class', node.name))

            for child in node.body:
                visit(child)

            stack.pop()
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent_kind = stack[-1][0] if stack else ''
            nested = parent_kind in ('function', 'method', 'nested')

            if nested:
                # Keep calls inside local helpers attributed to the nearest
                # Forge-addressable outer function/method, but do not create
                # a fake top-level target such as file.py::add.
                stack.append(('nested', stack[-1][1]))

                for child in node.body:
                    visit(child)

                stack.pop()
                return

            in_class = parent_kind == 'class'
            kind = 'method' if in_class else 'function'
            target = add_definition(node, node.name, kind)

            if kind == 'method':
                stack.append(
                    ('method', target.split('::', 1)[1])
                )
            else:
                stack.append(('function', node.name))

            for child in node.body:
                visit(child)

            stack.pop()
            return

        if isinstance(node, ast.Import):
            for item in node.names:
                imports.append({
                    'module': item.name,
                    'name': item.asname or item.name.split('.')[0],
                    'path': _resolve_module(
                        root,
                        file_abs,
                        item.name,
                        level=0,
                    ),
                    'line': int(getattr(node, 'lineno', 1)),
                    'scope': _scope_target(rel, stack),
                })

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            resolved = _resolve_module(
                root,
                file_abs,
                module,
                level=int(getattr(node, 'level', 0) or 0),
            )

            for item in node.names:
                imports.append({
                    'module': module,
                    'name': item.asname or item.name,
                    'imported': item.name,
                    'path': resolved,
                    'line': int(getattr(node, 'lineno', 1)),
                    'scope': _scope_target(rel, stack),
                })

        elif isinstance(node, ast.Call):
            name = _call_name(node)

            if name:
                calls.append({
                    'name': name,
                    'path': rel,
                    'line': int(getattr(node, 'lineno', 1)),
                    'scope': _scope_target(rel, stack),
                })

        for child in ast.iter_child_nodes(node):
            visit(child)

    for child in tree.body:
        visit(child)

    return {
        'path': rel,
        'error': '',
        'definitions': definitions,
        'imports': imports,
        'calls': calls,
    }


def build_index(project_root, scope):
    """Build an in-memory static relationship index."""
    root = os.path.abspath(project_root)
    scope_abs = scope

    if not os.path.isabs(scope_abs):
        scope_abs = os.path.join(root, scope_abs)

    scope_abs = os.path.abspath(scope_abs)

    files = []
    definitions = []
    imports = []
    calls = []
    errors = []

    for file_abs in _python_files(root, scope_abs):
        row = _parse_file(root, file_abs)
        files.append(row.get('path') or _rel(root, file_abs))

        if row.get('error'):
            errors.append({
                'path': row.get('path') or _rel(root, file_abs),
                'error': row.get('error'),
            })

        definitions.extend(row.get('definitions') or [])
        imports.extend(row.get('imports') or [])
        calls.extend(row.get('calls') or [])

    defs_by_name = {}
    defs_by_target = {}

    for row in definitions:
        defs_by_name.setdefault(
            row.get('name') or '',
            [],
        ).append(row)

        defs_by_target[row.get('target') or ''] = row

    reverse_import_map = {}
    reverse_import_seen = set()

    for row in imports:
        target_path = row.get('path') or ''

        if not target_path:
            continue

        importing_scope = row.get('scope') or ''
        edge = (
            target_path,
            importing_scope,
            int(row.get('line') or 0),
            row.get('module') or '',
        )

        if edge in reverse_import_seen:
            continue

        reverse_import_seen.add(edge)

        reverse_import_map.setdefault(
            target_path,
            [],
        ).append({
            'path': importing_scope.split('::', 1)[0],
            'scope': importing_scope,
            'line': row.get('line') or 0,
            'module': row.get('module') or '',
        })

    return {
        'root': root,
        'scope': _rel(root, scope_abs),
        'files': files,
        'definitions': definitions,
        'imports': imports,
        'calls': calls,
        'errors': errors,
        'defs_by_name': defs_by_name,
        'defs_by_target': defs_by_target,
        'reverse_imports': reverse_import_map,
    }


def reverse_imports(index, path):
    return list(
        (index.get('reverse_imports') or {}).get(path) or []
    )


def callers(index, target, include_candidates=False):
    """
    Return statically resolved call sites for a Forge AST target.

    Resolution currently understands:
    - unqualified calls to definitions in the same file
    - self.method(...) / cls.method(...) within the defining class
    - from module import symbol [as alias]
    - import module [as alias] followed by module.symbol(...)

    Set include_candidates=True to additionally include unresolved terminal-name
    matches. Those rows are explicitly labelled ``candidate``.
    """
    definition = (
        index.get('defs_by_target') or {}
    ).get(target)

    if not definition:
        return []

    wanted = definition.get('name') or ''
    definition_path = definition.get('path') or ''
    definition_kind = definition.get('kind') or ''

    target_tail = (
        target.split('::', 1)[1]
        if '::' in target
        else ''
    )

    owner_class = ''

    if definition_kind == 'method' and '.' in target_tail:
        owner_class = target_tail.split('.', 1)[0]

    imports_by_source = {}

    for row in index.get('imports') or []:
        importing_scope = row.get('scope') or ''
        importing_path = importing_scope.split('::', 1)[0]

        imports_by_source.setdefault(
            importing_path,
            [],
        ).append(row)

    rows = []
    seen = set()

    def emit(call, confidence):
        key = (
            call.get('path') or '',
            int(call.get('line') or 0),
            call.get('scope') or '',
            call.get('name') or '',
        )

        if key in seen:
            return

        seen.add(key)

        rows.append({
            'caller': call.get('scope') or call.get('path') or '',
            'call': call.get('name') or '',
            'path': call.get('path') or '',
            'line': call.get('line') or 0,
            'confidence': confidence,
        })

    def import_visible(import_row, call):
        import_scope = import_row.get('scope') or ''
        call_scope = call.get('scope') or ''
        call_path = call.get('path') or ''

        # Module-level import.
        if import_scope == call_path:
            return True

        # Function/method-local import.
        return import_scope == call_scope

    for call in index.get('calls') or []:
        name = call.get('name') or ''
        call_path = call.get('path') or ''
        resolved = False

        if call_path == definition_path:
            if definition_kind == 'method':
                caller_scope = call.get('scope') or ''
                caller_tail = (
                    caller_scope.split('::', 1)[1]
                    if '::' in caller_scope
                    else ''
                )
                caller_class = (
                    caller_tail.split('.', 1)[0]
                    if '.' in caller_tail
                    else ''
                )

                if (
                    owner_class
                    and caller_class == owner_class
                    and name in (
                        'self.' + wanted,
                        'cls.' + wanted,
                    )
                ):
                    emit(call, 'same-class')
                    resolved = True

            if not resolved and name == wanted:
                emit(call, 'same-file')
                resolved = True

        if not resolved:
            for import_row in imports_by_source.get(
                call_path,
                [],
            ):
                if not import_visible(import_row, call):
                    continue

                if (import_row.get('path') or '') != definition_path:
                    continue

                imported = import_row.get('imported') or ''
                binding = import_row.get('name') or ''
                module = import_row.get('module') or ''

                if imported:
                    if imported == wanted and name == binding:
                        emit(call, 'import')
                        resolved = True
                        break

                else:
                    expected = []

                    if binding:
                        expected.append(binding + '.' + wanted)

                    if module:
                        expected.append(module + '.' + wanted)

                    if name in expected:
                        emit(call, 'module-import')
                        resolved = True
                        break

        if (
            not resolved
            and include_candidates
            and name.split('.')[-1] == wanted
        ):
            emit(call, 'candidate')

    return rows


def summary(index):
    return {
        'scope': index.get('scope') or '',
        'files': len(index.get('files') or []),
        'definitions': len(index.get('definitions') or []),
        'imports': len(index.get('imports') or []),
        'calls': len(index.get('calls') or []),
        'local_import_edges': sum(
            1
            for row in index.get('imports') or []
            if row.get('path')
        ),
        'errors': len(index.get('errors') or []),
    }