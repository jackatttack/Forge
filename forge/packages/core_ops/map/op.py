# -*- coding: utf-8 -*-
"""
MAP core op.

Show structure, not full contents.

MAP is READ's cousin:
- READ shows content.
- SEARCH finds matches.
- MAP shows shape and useful next inspection targets.
"""

import ast
import os

from forge.core.file_safety import safe_target, read_text


SPEC = {
    'name': 'MAP',
    'target_kind': 'path',
    'body_mode': 'forbidden',
    'allowed_directives': set(['MODE', 'DEPTH', 'LIMIT', 'DOCS']),
    'required_directives': set(),
}


HELP = {
    'summary': 'Map project, directory, Python-file structure, and opt-in code relationships without dumping full contents.',
    'minimal_example': [
        'MAP forge',
        '',
        'MAP forge',
        'DEPTH: 2',
        '',
        'MAP forge/forge/core/runner.py',
        '',
        'MAP forge/forge/core/runner.py',
        'MODE: imports',
        '',
        'MAP forge/forge/core/runner.py',
        'MODE: targets',
        '',
        'MAP forge/forge/core/runner.py',
        'MODE: relationships',
    ],
    'directives': {
        'DEPTH': (
            'Directory depth from 1 to 5; '
            'the default is 1.'
        ),
        'DOCS': (
            'Include README and docstring hints; '
            'the default is yes.'
        ),
        'LIMIT': (
            'Maximum listed rows; '
            'the default is 80.'
        ),
        'MODE': (
            'Choose auto, targets, imports, '
            'or relationships.'
        ),
    },
    'common_failures': [
        'Missing target path.',
        'Using MAP when full source content is needed. Use READ for contents.',
        'Expecting MAP to search for arbitrary text. Use SEARCH for locating matches.',
        'Expecting MODE: relationships to prove dynamic Python dispatch. It reports statically resolved relationships only.',
    ],
    'safe_usage': [
        'Use MAP before broad READ on unfamiliar projects.',
        'Use MAP on directories for navigation and package shape.',
        'Use MAP on Python files for imports and READ-ready targets.',
        'Use MODE: imports for dependency-focused view (suppresses targets).',
        'Use MODE: targets for target-focused view (suppresses imports).',
        'Use MODE: relationships on a Python file for reverse imports and statically resolved external callers.',
        'Use SEARCH when looking for a specific symbol or phrase.',
    ],
    'related_ops': ['READ', 'SEARCH'],
}


HINTS = {
    '_max_hints': 1,
    'target': {
        'message': 'MAP needs a path target.',
        'why': 'MAP describes the structure or relationships of a file or directory.',
        'example': [
            'MAP forge',
            '',
            'MAP forge/forge/core/runner.py',
        ],
        'next': [
            'Use MAP on a directory for a project overview.',
            'Use MAP on a Python file for imports, targets, or relationships.',
        ],
    },
    'mode': {
        'message': 'MAP MODE must be auto, targets, imports, or relationships.',
        'why': 'MAP has a small set of focused structural views.',
        'example': [
            'MAP forge/forge/core/runner.py',
            'MODE: imports',
            '',
            'MAP forge/forge/core/runner.py',
            'MODE: targets',
            '',
            'MAP forge/forge/core/runner.py',
            'MODE: relationships',
        ],
        'next': ['Use MODE: auto unless you need a focused view.'],
    },
}


_STDLIBISH = set([
    'abc', 'argparse', 'ast', 'base64', 'binascii', 'bisect',
    'collections', 'concurrent', 'configparser', 'contextlib', 'copy', 'csv',
    'dataclasses', 'datetime', 'decimal', 'difflib', 'enum',
    'fractions', 'functools', 'glob',
    'hashlib', 'heapq', 'html', 'http',
    'importlib', 'inspect', 'io', 'itertools',
    'json', 'logging',
    'math', 'mimetypes', 'multiprocessing',
    'operator', 'os',
    'pathlib', 'pickle', 'platform', 'plistlib', 'pprint',
    'queue', 'random', 're',
    'secrets', 'shlex', 'shutil', 'signal', 'socket', 'sqlite3',
    'statistics', 'string', 'struct', 'subprocess', 'sys',
    'tempfile', 'textwrap', 'threading', 'time', 'timeit', 'token', 'tokenize',
    'traceback', 'types', 'typing',
    'unicodedata', 'unittest', 'urllib', 'uuid',
    'warnings', 'weakref',
    'xml', 'zipfile', 'zlib',
])


_ENTRYPOINT_NAME_SCORES = {
    '__main__.py': 55,
    'main.py': 40,
    'app.py': 30,
    'cli.py': 30,
    'entry.py': 24,
    'run.py': 24,
    'start.py': 24,
    'launcher.py': 24,
    'server.py': 24,
}

_ENTRYPOINT_NAMES = set(
    _ENTRYPOINT_NAME_SCORES
)


_README_NAMES = set([
    'README',
    'README.txt',
    'README.md',
    'readme.txt',
    'readme.md',
])


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _truthy(value, default=True):
    text = str(value if value is not None else '').strip().lower()
    if not text:
        return bool(default)
    return text in ('1', 'yes', 'y', 'true', 'on')


def _mode(parsed_op):
    directives = parsed_op.get('directives') or {}
    return str(directives.get('MODE') or 'auto').strip().lower() or 'auto'

def _preview_sections(lines):
    data = {
        'fields': {},
        'sections': {},
        'map_target': '',
        'map_type': '',
    }

    current = None

    for raw in list(lines or []):
        line = str(raw or '').rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith('MAP '):
            data['map_target'] = stripped[4:].strip()
            current = None
            continue

        if stripped.startswith('TYPE='):
            data['map_type'] = stripped.split('=', 1)[1].strip()
            current = None
            continue

        if stripped.endswith(':') and not stripped.startswith('-'):
            current = stripped[:-1]
            data['sections'].setdefault(current, [])
            continue

        if current:
            data['sections'].setdefault(current, []).append(line)
            continue

        if ':' in stripped:
            key, value = stripped.split(':', 1)
            data['fields'][key.strip().lower()] = value.strip()

    return data


def _section_rows(map_data, name):
    return list(((map_data or {}).get('sections') or {}).get(name) or [])


def _command_rows(map_data):
    rows = []
    for name in (
        'Suggested next reads',
        'Suggested dependency maps',
        'Suggested next steps',
    ):
        for row in _section_rows(map_data, name):
            text = str(row or '').strip()
            if text.startswith('- '):
                text = text[2:].strip()
            if text:
                rows.append(text)
    return rows


def _local_dependency_rows(map_data):
    rows = []
    for row in _section_rows(map_data, 'Suggested dependency maps'):
        text = str(row or '').strip()
        if text.startswith('- MAP '):
            rows.append(text[6:].strip())
    return rows


def _target_rows_from_preview(map_data):
    return _section_rows(map_data, 'Targets') + _section_rows(map_data, 'Target highlights')


def _import_rows_from_preview(map_data):
    return _section_rows(map_data, 'Imports') + _section_rows(map_data, 'Import summary')


def _shape_summary(map_data):
    fields = (map_data or {}).get('fields') or {}
    summary = {}
    for key in ('files', 'dirs', 'python files', 'lines', 'imports', 'targets'):
        value = fields.get(key)
        if value is None:
            continue
        try:
            summary[key.replace(' ', '_')] = int(str(value).strip())
        except Exception:
            summary[key.replace(' ', '_')] = value
    return summary

def _agent_commands(map_data):
    commands = _command_rows(map_data)
    reads = []
    maps = []
    seen_reads = set()
    seen_maps = set()

    for cmd in commands:
        text = str(cmd or '').strip()
        if text.startswith('READ ') and text not in seen_reads:
            reads.append(text)
            seen_reads.add(text)
        elif text.startswith('MAP ') and text not in seen_maps:
            maps.append(text)
            seen_maps.add(text)

    return reads, maps


def _role_from_path(target, kind, map_data):
    target = str(target or '').replace('\\', '/')
    lower = target.lower()
    kind = str(kind or '').strip().lower()
    sections = (map_data or {}).get('sections') or {}
    fields = (map_data or {}).get('fields') or {}

    if kind == 'directory':
        if '/core_ops/' in lower or '/custom_ops/' in lower:
            return 'op_package'
        if lower.endswith('/docs') or '/docs/' in lower:
            return 'docs'
        if 'smoke' in lower or 'test' in lower:
            return 'smokes'
        if lower.startswith('archive/') or '/archive/' in lower:
            return 'archive_reference'
        if lower.startswith('projects/') and lower.count('/') <= 1:
            return 'project_root'
        return 'directory'

    name = target.rsplit('/', 1)[-1]

    if name in ('op.py', 'manifest.py') and ('/core_ops/' in lower or '/custom_ops/' in lower):
        return 'op_file'
    if name == 'pages.py' and ('/core_ops/' in lower or '/custom_ops/' in lower):
        return 'surface_page'
    if 'renderer' in lower or '/render/' in lower:
        return 'renderer'
    if '/components/' in lower or '/component' in lower:
        return 'component'
    if 'smoke' in lower or 'test_' in lower or lower.endswith('_test.py'):
        return 'smoke'
    if name in ('entry.py', 'main.py', 'launcher.py') or name.startswith('run_'):
        return 'launcher'
    if name.upper() in ('README.TXT', 'README.MD', 'HANDOFF.TXT', 'PROJECT_CONTROL.TXT', 'ROADMAP.TXT'):
        return 'project_doc'
    if kind == 'python-file':
        target_rows = sections.get('Targets') or sections.get('Target highlights') or []
        joined = '\n'.join(str(x) for x in target_rows)
        if 'render_' in joined or '_render' in joined:
            return 'renderer_like_python'
        if 'execute' in joined and 'SPEC' in joined:
            return 'op_like_python'
        return 'python_file'

    if str(fields.get('path') or '').lower().endswith(('.txt', '.md', '.rst')):
        return 'doc_file'

    return kind or 'unknown'


def _agent_warnings(target, kind, map_data):
    warnings = []
    target = str(target or '').replace('\\', '/')
    lower = target.lower()
    fields = (map_data or {}).get('fields') or {}
    sections = (map_data or {}).get('sections') or {}

    parts = set(
        part
        for part in lower.strip('/').split('/')
        if part
    )

    if parts.intersection({
        'archive',
        'archives',
        'archived',
        'backup',
        'backups',
    }):
        warnings.append(
            'archive/backup-looking path'
        )

    if parts.intersection({
        'test',
        'tests',
        'testing',
        'fixture',
        'fixtures',
    }):
        warnings.append(
            'test/fixture-looking path'
        )

    if parts.intersection({
        'generated',
        'vendor',
        'vendored',
        'third_party',
        'third-party',
    }):
        warnings.append(
            'generated/vendor-looking path'
        )
    if fields.get('scale'):
        warnings.append(str(fields.get('scale')))
    if kind == 'python-file' and not sections.get('Suggested next reads'):
        warnings.append('no suggested target reads found')

    return warnings


def _agent_data(target, kind, map_data):
    reads, maps = _agent_commands(map_data)
    warnings = _agent_warnings(target, kind, map_data)
    fields = (map_data or {}).get('fields') or {}

    return {
        'role': _role_from_path(target, kind, map_data),
        'suggested_reads': reads,
        'suggested_maps': maps,
        'large_file': bool(fields.get('scale')),
        'warnings': warnings,
    }


def _relationship_scope(root, abs_path):
    """
    Choose a bounded project scope for relationship indexing.

    Prefer the nearest ancestor that looks like an actual project root. This
    works for ordinary repositories and nested projects/monorepos without
    knowing anything about a particular workspace layout.

    If no project marker exists, fall back to the containing directory.
    """
    root_abs = os.path.abspath(
        root
    )

    path_abs = os.path.abspath(
        abs_path
    )

    if os.path.isdir(
        path_abs
    ):
        current = path_abs
    else:
        current = os.path.dirname(
            path_abs
        )

    markers = {
        'pyproject.toml',
        'setup.py',
        'setup.cfg',
        'requirements.txt',
        'package.json',
        'cargo.toml',
        'go.mod',
        'gemfile',
        'composer.json',
        'readme',
        'readme.md',
        'readme.txt',
        '.git',
    }

    while True:
        try:
            names = set(
                name.lower()
                for name in os.listdir(
                    current
                )
            )
        except Exception:
            names = set()

        if names.intersection(
            markers
        ):
            scope = os.path.relpath(
                current,
                root_abs,
            ).replace(
                os.sep,
                '/',
            )

            return (
                '.'
                if scope == '.'
                else scope
            )

        if current == root_abs:
            break

        parent = os.path.dirname(
            current
        )

        if (
            parent == current
            or not (
                parent == root_abs
                or parent.startswith(
                    root_abs
                    + os.sep
                )
            )
        ):
            break

        current = parent

    rel = _rel(
        root_abs,
        abs_path,
    ).replace(
        os.sep,
        '/',
    )

    parent = os.path.dirname(
        rel
    ).replace(
        os.sep,
        '/',
    )

    return parent or '.'


def _render_python_relationships(root, abs_path, target, limit):
    """
    Render opt-in whole-project relationships for one Python file.

    Import codegraph lazily so normal MAP modes remain independent from the
    relationship engine.
    """
    from forge.core.codegraph import (
        build_index,
        callers,
        reverse_imports,
        summary,
    )

    rel = _rel(root, abs_path)
    scope = _relationship_scope(root, abs_path)
    index = build_index(root, scope)
    info = summary(index)

    definitions = [
        row
        for row in index.get('definitions') or []
        if row.get('path') == rel
    ]

    reverse_rows = reverse_imports(index, rel)

    lines = [
        'MAP %s' % target,
        'TYPE=python-relationships',
        'path: ' + rel,
        'graph scope: ' + scope,
        'indexed files: %d' % info.get('files', 0),
        'definitions: %d' % len(definitions),
        'reverse imports: %d' % len(reverse_rows),
        'graph errors: %d' % info.get('errors', 0),
    ]

    lines.append('')
    lines.append('Reverse imports:')

    if reverse_rows:
        for row in reverse_rows[:limit]:
            lines.append(
                '- %s:%s · %s'
                % (
                    row.get('path') or '?',
                    row.get('line') or 0,
                    row.get('scope') or '',
                )
            )

        if len(reverse_rows) > limit:
            lines.append(
                '- ... %d more reverse import(s)'
                % (len(reverse_rows) - limit)
            )
    else:
        lines.append('- none found')

    relationship_rows = []

    for definition in definitions:
        target_ref = definition.get('target') or ''

        if not target_ref:
            continue

        caller_rows = [
            row
            for row in callers(index, target_ref)
            if row.get('path') != rel
        ]

        if not caller_rows:
            continue

        caller_files = sorted(set(
            row.get('path') or ''
            for row in caller_rows
            if row.get('path')
        ))

        relationship_rows.append({
            'target': target_ref,
            'kind': definition.get('kind') or '',
            'name': definition.get('name') or '',
            'calls': len(caller_rows),
            'files': caller_files,
        })

    relationship_rows.sort(
        key=lambda row: (
            -int(row.get('calls') or 0),
            row.get('name') or '',
        )
    )

    lines.append('')
    lines.append('Resolved external callers:')

    if relationship_rows:
        for row in relationship_rows[:limit]:
            files = row.get('files') or []
            preview = ', '.join(files[:4])

            if len(files) > 4:
                preview += ', +%d more' % (len(files) - 4)

            lines.append(
                '- %s · %s · %d resolved call(s) across %d file(s)'
                % (
                    row.get('kind') or '?',
                    row.get('target') or row.get('name') or '?',
                    row.get('calls') or 0,
                    len(files),
                )
            )

            if preview:
                lines.append('  - ' + preview)

        if len(relationship_rows) > limit:
            lines.append(
                '- ... %d more externally referenced definition(s)'
                % (len(relationship_rows) - limit)
            )
    else:
        lines.append('- none found')

    lines.append('')
    lines.append(
        'note: relationships are statically resolved; '
        'dynamic dispatch and runtime-generated imports may not be visible.'
    )

    return lines


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    if not target:
        errors.append('MAP requires a target path')

    mode = _mode(parsed_op)
    if mode not in ('auto', 'targets', 'imports', 'relationships'):
        errors.append(
            'MAP MODE must be auto, targets, imports, or relationships, got: '
            + mode
        )

    directives = parsed_op.get('directives') or {}

    depth = _as_int(directives.get('DEPTH'), 1)
    if depth < 0:
        errors.append('MAP DEPTH must be >= 0')
    elif depth > 5:
        errors.append('MAP DEPTH must be <= 5')

    limit = _as_int(directives.get('LIMIT'), 80)
    if limit < 1:
        errors.append('MAP LIMIT must be >= 1')

    return errors


def _rel(root, path):
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path


def _is_python(path):
    return os.path.splitext(path)[1].lower() == '.py'


def _first_meaningful_line(text):
    for line in (text or '').splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#'):
            stripped = stripped.lstrip('#').strip()
        if stripped:
            return stripped[:140]
    return ''


def _read_doc_hint(path):
    try:
        return _first_meaningful_line(read_text(path))
    except Exception:
        return ''

def _clean_hint_value(value):
    value = str(value or '').strip()
    if not value:
        return ''
    for sep in ('#', '  '):
        if sep in value:
            value = value.split(sep, 1)[0].strip()
    return value.strip('`*[]() ')


def _hint_to_project_rel(root, base_dir_abs, value):
    value = _clean_hint_value(value)
    if not value:
        return ''

    lowered = value.lower()
    if lowered.startswith(('http://', 'https://', 'mailto:')):
        return ''

    candidate = os.path.normpath(os.path.join(base_dir_abs, value))
    if os.path.isfile(candidate) or os.path.isdir(candidate):
        return _rel(root, candidate)

    candidate = os.path.normpath(os.path.join(root, value))
    if os.path.isfile(candidate) or os.path.isdir(candidate):
        return _rel(root, candidate)

    return ''


def _read_project_hints(root, readme_path):
    hints = {'entrypoints': []}

    if not readme_path:
        return hints

    try:
        text = read_text(readme_path)
    except Exception:
        return hints

    base_dir = os.path.dirname(readme_path)
    prefixes = (
        'entry point:',
        'entrypoint:',
        'entry:',
        'main:',
        'run:',
        'start:',
    )

    for raw in text.splitlines()[:80]:
        line = str(raw or '').strip()
        if not line:
            continue

        lowered = line.lower().lstrip('-* ').strip()
        for prefix in prefixes:
            if lowered.startswith(prefix):
                value = line.split(':', 1)[1].strip() if ':' in line else ''
                rel = _hint_to_project_rel(root, base_dir, value)
                if rel and rel not in hints['entrypoints']:
                    hints['entrypoints'].append(rel)

    return hints



def _normal_rel(path):
    return str(
        path
        or ''
    ).replace(
        '\\',
        '/',
    )


def _entrypoint_path_context(
    abs_dir,
    path,
):
    """
    Return generic location evidence.

    Negative contexts are penalties, not exclusions. Strong project metadata
    or documentation can still surface an unusual but deliberate entrypoint.
    """
    rel = _normal_rel(
        os.path.relpath(
            path,
            abs_dir,
        )
    )

    parts = [
        part.lower()
        for part in rel.split('/')
        if part
    ]

    filename = (
        parts[-1]
        if parts
        else ''
    )

    dirs = set(
        parts[:-1]
    )

    score = 0
    reasons = []

    depth = max(
        0,
        len(parts) - 1,
    )

    if depth == 0:
        score += 15
        reasons.append(
            'root-level file'
        )

    elif depth == 1:
        score += 8
        reasons.append(
            'shallow path'
        )

    penalty_groups = [
        (
            {
                'archive',
                'archives',
                'archived',
                'backup',
                'backups',
            },
            -100,
            'archive/backup path',
        ),
        (
            {
                'test',
                'tests',
                'testing',
                'fixture',
                'fixtures',
                'mock',
                'mocks',
            },
            -100,
            'test/fixture path',
        ),
        (
            {
                'generated',
                'vendor',
                'vendored',
                'third_party',
                'third-party',
            },
            -100,
            'generated/vendor path',
        ),
        (
            {
                'scratch',
                'tmp',
                'temp',
                'temporary',
            },
            -80,
            'scratch/temp path',
        ),
        (
            {
                'smoke',
                'smokes',
                'probe',
                'probes',
                'benchmark',
                'benchmarks',
                'bench',
            },
            -70,
            'probe/benchmark path',
        ),
        (
            {
                'migration',
                'migrations',
            },
            -45,
            'migration path',
        ),
        (
            {
                'example',
                'examples',
                'demo',
                'demos',
            },
            -25,
            'example/demo path',
        ),
    ]

    for names, penalty, reason in penalty_groups:
        if dirs.intersection(
            names
        ):
            score += penalty
            reasons.append(
                reason
            )

    if (
        filename.startswith(
            'test_'
        )
        or filename.endswith(
            '_test.py'
        )
    ):
        score -= 100
        reasons.append(
            'test filename'
        )

    stem = os.path.splitext(
        filename
    )[0]

    if any(
        token in stem
        for token in (
            'smoke',
            'probe',
            'benchmark',
        )
    ):
        score -= 70
        reasons.append(
            'probe/benchmark filename'
        )

    return (
        score,
        reasons,
    )


def _literal_text(node):
    if isinstance(
        node,
        ast.Str,
    ):
        return node.s

    value = getattr(
        node,
        'value',
        None,
    )

    if isinstance(
        value,
        str,
    ):
        return value

    return None


def _is_name_node(
    node,
    expected,
):
    return (
        isinstance(
            node,
            ast.Name,
        )
        and node.id == expected
    )


def _is_main_guard_test(node):
    if not isinstance(
        node,
        ast.Compare,
    ):
        return False

    if (
        len(
            node.ops
        )
        != 1
        or not isinstance(
            node.ops[0],
            ast.Eq,
        )
        or len(
            node.comparators
        )
        != 1
    ):
        return False

    left = node.left
    right = node.comparators[0]

    return (
        (
            _is_name_node(
                left,
                '__name__',
            )
            and _literal_text(
                right
            )
            == '__main__'
        )
        or
        (
            _is_name_node(
                right,
                '__name__',
            )
            and _literal_text(
                left
            )
            == '__main__'
        )
    )


def _python_entrypoint_signals(path):
    signals = {
        'main_guard': False,
        'main_callable': False,
        'python_shebang': False,
    }

    try:
        if os.path.getsize(
            path
        ) > 512 * 1024:
            return signals
    except Exception:
        pass

    try:
        text = read_text(
            path
        )
    except Exception:
        return signals

    first = (
        text.splitlines()[0]
        if text.splitlines()
        else ''
    )

    if (
        first.startswith(
            '#!'
        )
        and 'python'
        in first.lower()
    ):
        signals[
            'python_shebang'
        ] = True

    try:
        tree = ast.parse(
            text,
            filename=path,
        )
    except Exception:
        return signals

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            if node.name in (
                'main',
                'cli',
            ):
                signals[
                    'main_callable'
                ] = True

    for node in ast.walk(
        tree
    ):
        if (
            isinstance(
                node,
                ast.If,
            )
            and _is_main_guard_test(
                node.test
            )
        ):
            signals[
                'main_guard'
            ] = True
            break

    return signals


def _module_names_for_python_file(
    abs_dir,
    path,
):
    rel = _normal_rel(
        os.path.relpath(
            path,
            abs_dir,
        )
    )

    if not rel.endswith(
        '.py'
    ):
        return []

    parts = rel[:-3].split(
        '/'
    )

    names = []

    def add(parts_value):
        parts_value = list(
            parts_value
        )

        if (
            parts_value
            and parts_value[-1]
            == '__init__'
        ):
            parts_value = (
                parts_value[:-1]
            )

        if not parts_value:
            return

        value = '.'.join(
            parts_value
        )

        if (
            value
            and value not in names
        ):
            names.append(
                value
            )

    add(
        parts
    )

    if (
        parts
        and parts[0]
        == 'src'
    ):
        add(
            parts[1:]
        )

    return names


def _module_lookup(
    abs_dir,
    py_files,
):
    lookup = {}

    for path in py_files:
        for module_name in (
            _module_names_for_python_file(
                abs_dir,
                path,
            )
        ):
            lookup.setdefault(
                module_name,
                path,
            )

    return lookup


def _clean_module_reference(value):
    value = str(
        value
        or ''
    ).strip()

    if not value:
        return ''

    if '#' in value:
        value = value.split(
            '#',
            1,
        )[0].strip()

    value = value.rstrip(
        ','
    ).strip()

    value = value.strip(
        '"\'` '
    )

    if not value:
        return ''

    if value.startswith(
        '{'
    ):
        return ''

    if ':' in value:
        value = value.split(
            ':',
            1,
        )[0].strip()

    value = value.strip(
        '"\'` '
    )

    allowed = (
        value.replace(
            '.',
            ''
        )
        .replace(
            '_',
            ''
        )
        .isalnum()
    )

    if not allowed:
        return ''

    return value


def _project_metadata_entrypoints(
    abs_dir,
    py_files,
):
    """
    Return path -> evidence labels from common Python project metadata.

    Parsing is intentionally small and dependency-free. MAP only needs enough
    TOML/INI awareness to recognise ordinary static script declarations.
    """
    found = {}
    modules = _module_lookup(
        abs_dir,
        py_files,
    )

    def add_module(
        module_name,
        reason,
    ):
        path = modules.get(
            module_name
        )

        if not path:
            return

        labels = found.setdefault(
            path,
            [],
        )

        if reason not in labels:
            labels.append(
                reason
            )

    pyproject = os.path.join(
        abs_dir,
        'pyproject.toml',
    )

    if os.path.isfile(
        pyproject
    ):
        try:
            text = read_text(
                pyproject
            )
        except Exception:
            text = ''

        section = ''

        script_sections = {
            'project.scripts',
            'project.gui-scripts',
            'tool.poetry.scripts',
        }

        for raw in text.splitlines():
            line = raw.strip()

            if not line:
                continue

            if (
                line.startswith(
                    '['
                )
                and line.endswith(
                    ']'
                )
            ):
                section = line.strip(
                    '[] '
                ).lower()
                continue

            if (
                section
                not in script_sections
                or '='
                not in line
            ):
                continue

            _name, value = line.split(
                '=',
                1,
            )

            module_name = (
                _clean_module_reference(
                    value
                )
            )

            if module_name:
                add_module(
                    module_name,
                    'project script metadata',
                )

    setup_cfg = os.path.join(
        abs_dir,
        'setup.cfg',
    )

    if os.path.isfile(
        setup_cfg
    ):
        try:
            text = read_text(
                setup_cfg
            )
        except Exception:
            text = ''

        section = ''

        for raw in text.splitlines():
            line = raw.strip()

            if not line:
                continue

            if (
                line.startswith(
                    '['
                )
                and line.endswith(
                    ']'
                )
            ):
                section = line.strip(
                    '[] '
                ).lower()
                continue

            if (
                section
                != 'options.entry_points'
                or '='
                not in line
            ):
                continue

            left, value = line.split(
                '=',
                1,
            )

            if left.strip().lower() in (
                'console_scripts',
                'gui_scripts',
            ):
                if not value.strip():
                    continue

            module_name = (
                _clean_module_reference(
                    value
                )
            )

            if module_name:
                add_module(
                    module_name,
                    'setup.cfg entry point',
                )

    return found


def _readme_entrypoint_evidence(
    root,
    abs_dir,
    readme_path,
    py_files,
):
    found = {}

    if not readme_path:
        return found

    try:
        text = read_text(
            readme_path
        )
    except Exception:
        return found

    basename_counts = {}

    for path in py_files:
        basename = os.path.basename(
            path
        ).lower()

        basename_counts[
            basename
        ] = (
            basename_counts.get(
                basename,
                0,
            )
            + 1
        )

    modules = _module_lookup(
        abs_dir,
        py_files,
    )

    def add(
        path,
        reason,
    ):
        labels = found.setdefault(
            path,
            [],
        )

        if reason not in labels:
            labels.append(
                reason
            )

    for raw in text.splitlines()[:240]:
        line = str(
            raw
            or ''
        ).strip()

        if not line:
            continue

        lowered = line.lower()

        commandish = any(
            token in lowered
            for token in (
                'python ',
                'python3 ',
                'run ',
                'start ',
                'launch ',
                'execute ',
            )
        )

        if commandish:
            normalized = (
                lowered
                .replace(
                    '`',
                    ''
                )
                .replace(
                    '"',
                    ''
                )
                .replace(
                    "'",
                    ''
                )
            )

            for path in py_files:
                local = _normal_rel(
                    os.path.relpath(
                        path,
                        abs_dir,
                    )
                ).lower()

                project_rel = _normal_rel(
                    _rel(
                        root,
                        path,
                    )
                ).lower()

                basename = os.path.basename(
                    path
                ).lower()

                matched = (
                    local in normalized
                    or project_rel in normalized
                    or (
                        basename_counts.get(
                            basename
                        )
                        == 1
                        and basename
                        in normalized
                    )
                )

                if matched:
                    add(
                        path,
                        'README run command',
                    )

        marker = 'python -m '

        if marker in lowered:
            after = lowered.split(
                marker,
                1,
            )[1].strip()

            module_name = (
                after.split()[0]
                if after
                else ''
            )

            module_name = module_name.strip(
                '`"\' ;'
            )

            path = modules.get(
                module_name
            )

            if path:
                add(
                    path,
                    'README python -m command',
                )

    return found


def _rank_entrypoints(
    root,
    abs_dir,
    py_files,
    readme_path,
    project_hints,
):
    explicit_paths = set()

    for rel_entry in (
        project_hints.get(
            'entrypoints'
        )
        or []
    ):
        path = os.path.abspath(
            os.path.join(
                root,
                rel_entry,
            )
        )

        if path in py_files:
            explicit_paths.add(
                path
            )

    metadata = (
        _project_metadata_entrypoints(
            abs_dir,
            py_files,
        )
    )

    readme_evidence = (
        _readme_entrypoint_evidence(
            root,
            abs_dir,
            readme_path,
            py_files,
        )
    )

    ranked = []

    for path in py_files:
        score = 0
        reasons = []
        primary = False

        def add(
            value,
            reason,
        ):
            nonlocal score

            score += value

            if (
                reason
                and reason
                not in reasons
            ):
                reasons.append(
                    reason
                )

        if path in explicit_paths:
            primary = True
            add(
                120,
                'README declared entrypoint',
            )

        metadata_reasons = metadata.get(
            path,
            [],
        )

        if metadata_reasons:
            primary = True

        for reason in metadata_reasons:
            add(
                140,
                reason,
            )

        readme_reasons = readme_evidence.get(
            path,
            [],
        )

        if readme_reasons:
            primary = True

        for reason in readme_reasons:
            add(
                90,
                reason,
            )

        name = os.path.basename(
            path
        ).lower()

        name_score = (
            _ENTRYPOINT_NAME_SCORES.get(
                name,
                0,
            )
        )

        if name_score:
            if name == '__main__.py':
                reason = (
                    'package __main__'
                )
            else:
                reason = (
                    'conventional entry filename'
                )

            add(
                name_score,
                reason,
            )

        signals = (
            _python_entrypoint_signals(
                path
            )
        )

        if signals.get(
            'main_guard'
        ):
            add(
                60,
                '__main__ guard',
            )

        if signals.get(
            'main_callable'
        ):
            add(
                8,
                'main/cli callable',
            )

        if signals.get(
            'python_shebang'
        ):
            add(
                12,
                'Python shebang',
            )

        context_score, context_reasons = (
            _entrypoint_path_context(
                abs_dir,
                path,
            )
        )

        score += context_score

        for reason in context_reasons:
            if reason not in reasons:
                reasons.append(
                    reason
                )

        negative_context = any(
            reason in {
                'archive/backup path',
                'test/fixture path',
                'generated/vendor path',
                'scratch/temp path',
                'probe/benchmark path',
                'migration path',
                'example/demo path',
                'test filename',
                'probe/benchmark filename',
            }
            for reason in context_reasons
        )

        # Structural evidence can make a candidate primary, but generic
        # archive/test/example context keeps it as a fallback unless stronger
        # README or package metadata explicitly points at it.
        if not negative_context:
            if name == '__main__.py':
                primary = True

            elif (
                name_score
                and signals.get(
                    'main_guard'
                )
            ):
                primary = True

        candidate = bool(
            primary
            or name_score
            or signals.get(
                'main_guard'
            )
            or signals.get(
                'main_callable'
            )
            or signals.get(
                'python_shebang'
            )
        )

        if not candidate:
            continue

        ranked.append({
            'score': score,
            'primary': primary,
            'path': path,
            'rel': _rel(
                root,
                path,
            ),
            'reasons': reasons,
        })

    ranked.sort(
        key=lambda row: (
            -int(
                row.get(
                    'score'
                )
                or 0
            ),
            str(
                row.get(
                    'rel'
                )
                or ''
            ),
        )
    )

    # Scores order candidates; evidence class decides confidence.
    #
    # A runnable guard, shebang, main() or conventional filename can still be
    # useful when a repository has no clearer entrypoint. Once genuine primary
    # evidence exists, those weaker runnable files stay out of the main list.
    primary_rows = [
        row
        for row in ranked
        if row.get(
            'primary'
        )
    ]

    if primary_rows:
        return primary_rows

    return ranked


def _source_suggestion_key(
    abs_dir,
    path,
):
    rel = _normal_rel(
        os.path.relpath(
            path,
            abs_dir,
        )
    )

    parts = [
        part
        for part in rel.split('/')
        if part
    ]

    name = (
        parts[-1].lower()
        if parts
        else ''
    )

    score = max(
        0,
        len(parts) - 1,
    ) * 5

    context_score, _reasons = (
        _entrypoint_path_context(
            abs_dir,
            path,
        )
    )

    if context_score < 0:
        score += abs(
            context_score
        )

    if name == '__init__.py':
        score += 80

    if name.startswith(
        '_'
    ):
        score += 25

    return (
        score,
        rel,
    )


def _find_readme(abs_dir):
    try:
        names = os.listdir(abs_dir)
    except Exception:
        return None

    for name in names:
        if name in _README_NAMES:
            path = os.path.join(abs_dir, name)
            if os.path.isfile(path):
                return path

    for name in names:
        if name.lower().startswith('readme'):
            path = os.path.join(abs_dir, name)
            if os.path.isfile(path):
                return path

    return None



def _module_doc(tree):
    try:
        return (ast.get_docstring(tree) or '').strip().splitlines()[0].strip()
    except Exception:
        return ''


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


def _range_text(node):
    start = getattr(node, 'lineno', 1)
    end = _end_lineno(node)
    if start == end:
        return '[%d]' % start
    return '[%d-%d]' % (start, end)


def _first_doc(node):
    try:
        raw = ast.get_docstring(node) or ''
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:90]
    except Exception:
        pass
    return ''


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
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts or []:
                collect(item)

    for target in targets:
        collect(target)

    return names


def _import_rows(tree):
    rows = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names or []:
                if alias.name:
                    rows.append({
                        'module': alias.name,
                        'name': alias.name,
                        'line': getattr(node, 'lineno', 1),
                        'text': 'import ' + alias.name,
                    })

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if getattr(node, 'level', 0):
                module = ('.' * int(node.level)) + module

            if module:
                rows.append({
                    'module': module,
                    'name': module,
                    'line': getattr(node, 'lineno', 1),
                    'text': 'from %s import ...' % module,
                })

            for alias in node.names or []:
                if module and alias.name:
                    full = module + '.' + alias.name
                else:
                    full = alias.name or module
                if full:
                    rows.append({
                        'module': module or full,
                        'name': full,
                        'line': getattr(node, 'lineno', 1),
                        'text': 'from %s import %s' % (module, alias.name),
                    })

    return rows


def _module_to_local_path(root, file_abs, module_name):
    module_name = str(module_name or '').strip()
    if not module_name or module_name.startswith('.'):
        return ''

    rel_parts = module_name.split('.')
    candidates = []

    def add_base(base):
        if not base:
            return
        candidates.append(os.path.join(base, *(rel_parts + ['__init__.py'])))
        candidates.append(os.path.join(base, *rel_parts) + '.py')

    # Project root first.
    add_base(root)

    # Then walk upward from the file's directory. This catches public Forge's
    # common shape where project_root is Documents but packages live under
    # Keep filesystem paths such as forge/core distinct from Python module names.
    current = os.path.dirname(os.path.abspath(file_abs))
    root_abs = os.path.abspath(root)
    seen = set()

    while current and current not in seen:
        seen.add(current)
        add_base(current)

        if current == root_abs:
            break

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    for path in candidates:
        if os.path.isfile(path):
            return _rel(root, path)

    return ''


def _classify_import(root, file_abs, module_name):
    top = str(module_name or '').lstrip('.').split('.')[0]
    local = _module_to_local_path(root, file_abs, module_name)

    if local:
        return 'local', local
    if top in _STDLIBISH:
        return 'stdlib', ''
    if module_name.startswith('.'):
        return 'relative', ''
    return 'external', ''


def _target_rows(root, file_abs, rel, tree):
    rows = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            target = '%s::%s.*' % (rel, node.name)
            rows.append({
                'kind': 'class',
                'name': node.name,
                'range': _range_text(node),
                'target': target,
                'doc': _first_doc(node),
                'indent': 0,
            })

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    rows.append({
                        'kind': 'method',
                        'name': '%s.%s' % (node.name, item.name),
                        'range': _range_text(item),
                        'target': '%s::%s.%s' % (rel, node.name, item.name),
                        'doc': _first_doc(item),
                        'indent': 1,
                    })
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    for name in _assignment_names(item):
                        rows.append({
                            'kind': 'assignment',
                            'name': '%s.%s' % (node.name, name),
                            'range': _range_text(item),
                            'target': '%s::%s.@%s' % (rel, node.name, name),
                            'doc': '',
                            'indent': 1,
                        })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append({
                'kind': 'function',
                'name': node.name,
                'range': _range_text(node),
                'target': '%s::%s' % (rel, node.name),
                'doc': _first_doc(node),
                'indent': 0,
            })

        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in _assignment_names(node):
                rows.append({
                    'kind': 'assignment',
                    'name': name,
                    'range': _range_text(node),
                    'target': '%s::@%s' % (rel, name),
                    'doc': '',
                    'indent': 0,
                })

    return rows


def _render_file_basic(root, abs_path, target, docs):
    rel = _rel(root, abs_path)
    try:
        text = read_text(abs_path)
    except Exception as e:
        return ['MAP %s' % target, 'TYPE=file', 'Could not read: %s: %s' % (type(e).__name__, e)]

    lines = [
        'MAP %s' % target,
        'TYPE=file',
        'path: ' + rel,
        'lines: %d' % len(text.splitlines()),
        'size: %d B' % len(text.encode('utf-8')),
    ]

    if docs:
        hint = _first_meaningful_line(text)
        if hint:
            lines.append('hint: ' + hint)

    lines.append('')
    lines.append('Suggested next reads:')
    lines.append('- READ %s' % rel)
    return lines


def _render_python_file(root, abs_path, target, mode, docs, limit):
    rel = _rel(root, abs_path)

    try:
        text = read_text(abs_path)
    except Exception as e:
        return ['MAP %s' % target, 'TYPE=python-file', 'Could not read: %s: %s' % (type(e).__name__, e)]

    source_lines = text.splitlines()

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [
            'MAP %s' % target,
            'TYPE=python-file',
            'path: ' + rel,
            'lines: %d' % len(source_lines),
            'syntax: SyntaxError: %s' % e,
            '',
            'Suggested next reads:',
            '- READ %s' % rel,
        ]

    imports = _import_rows(tree)
    targets = _target_rows(root, abs_path, rel, tree)

    line_count = len(source_lines)
    large_file = line_count > 700 or len(targets) > 35 or len(imports) > 40
    full_imports = mode == 'imports'
    full_targets = mode == 'targets'

    lines = [
        'MAP %s' % target,
        'TYPE=python-file',
        'path: ' + rel,
        'lines: %d' % line_count,
        'imports: %d' % len(imports),
        'targets: %d' % len(targets),
    ]

    if large_file:
        lines.append('scale: large file — compact structural summary')

    if docs:
        doc = _module_doc(tree)
        if doc:
            lines.append('doc: ' + doc[:140])

    def row_start(row):
        raw = str(row.get('range') or '[999999]').strip().strip('[]')
        try:
            return int(raw.split('-')[0])
        except Exception:
            return 999999

    def row_span(row):
        raw = str(row.get('range') or '[0-0]').strip().strip('[]')
        try:
            parts = raw.split('-')
            a = int(parts[0])
            b = int(parts[-1])
            return max(1, b - a + 1)
        except Exception:
            return 1

    import_seen = set()
    import_rows = []
    local_paths = []
    external_names = []
    stdlib_names = []
    relative_names = []

    for row in imports:
        name = row.get('name') or row.get('module') or ''
        if not name or name in import_seen:
            continue
        import_seen.add(name)
        kind, local = _classify_import(root, abs_path, row.get('module') or name)
        import_rows.append((row, kind, local, name))
        if kind == 'local' and local and local not in local_paths:
            local_paths.append(local)
        elif kind == 'external' and name not in external_names:
            external_names.append(name)
        elif kind == 'stdlib' and name not in stdlib_names:
            stdlib_names.append(name)
        elif kind == 'relative' and name not in relative_names:
            relative_names.append(name)

    show_imports = mode in ('auto', 'imports')
    show_targets = mode in ('auto', 'targets')

    if show_imports:
        if not imports:
            lines.append('')
            lines.append('Imports: none')
        elif full_imports or not large_file:
            lines.append('')
            lines.append('Imports:')
            count = 0
            for row, kind, local, name in import_rows:
                suffix = ' -> ' + local if local else ''
                lines.append('- line %04d · %-8s · %s%s' % (
                    int(row.get('line') or 0),
                    kind,
                    name,
                    suffix,
                ))
                count += 1
                if count >= limit:
                    lines.append('- ... import limit reached')
                    break
        else:
            lines.append('')
            lines.append('Import summary:')
            lines.append('- local modules: %d' % len(local_paths))
            lines.append('- stdlib imports: %d' % len(stdlib_names))
            lines.append('- external imports: %s' % (', '.join(external_names[:8]) if external_names else 'none'))
            if len(external_names) > 8:
                lines.append('- external overflow: %d more' % (len(external_names) - 8))
            if local_paths:
                lines.append('- top local dependencies:')
                for path in local_paths[:min(10, limit)]:
                    lines.append('  - ' + path)
                if len(local_paths) > min(10, limit):
                    lines.append('  - ... %d more local dependencies' % (len(local_paths) - min(10, limit)))
            lines.append('- Use MODE: imports for full import listing.')

    kind_counts = {}
    for row in targets:
        kind = row.get('kind') or '?'
        kind_counts[kind] = kind_counts.get(kind, 0) + 1

    def target_score(row):
        kind = row.get('kind') or ''
        name = row.get('name') or ''
        span = row_span(row)

        if kind == 'assignment' and name == 'SPEC':
            return 0
        if kind == 'assignment' and name == 'HELP':
            return 1
        if kind == 'assignment' and name == 'HINTS':
            return 2
        if name == 'validate':
            return 3
        if name == 'execute':
            return 4
        if name == 'main':
            return 5
        if name.endswith('.__init__') or name == '__init__':
            return 6
        if name.endswith('.layout') or name == 'layout':
            return 7
        if name.endswith('.draw') or name == 'draw':
            return 8
        if 'touch_' in name or '.touch_' in name:
            return 9
        if kind == 'class' and not name.startswith('_'):
            return 10
        if row.get('doc'):
            return 11
        if kind == 'function' and not name.startswith('_'):
            return 12
        if kind == 'method' and not name.startswith('_') and span <= 80:
            return 13
        if name.startswith('_render'):
            return 20
        if name.startswith('_apply') or 'apply' in name:
            return 21
        if name.startswith('_sync') or 'sync' in name:
            return 22
        if name.startswith('_'):
            return 30
        return 40

    ranked_targets = list(targets)
    ranked_targets.sort(key=lambda r: (
        target_score(r),
        -1 if row_span(r) > 40 else 0,
        row_start(r),
        r.get('name') or '',
    ))

    if show_targets:
        lines.append('')
        if not targets:
            lines.append('Targets: none')
        elif full_targets or not large_file:
            lines.append('Targets:')
            for idx, row in enumerate(targets):
                if idx >= limit:
                    lines.append('- ... target limit reached')
                    break
                pad = '  ' * int(row.get('indent') or 0)
                line = '- %s%-10s %-28s %-9s %s' % (
                    pad,
                    row.get('kind') or '',
                    row.get('name') or '',
                    row.get('range') or '',
                    row.get('target') or '',
                )
                if (
                    row.get('kind') == 'class'
                    and str(row.get('target') or '').endswith('.*')
                    and row_span(row) >= 300
                ):
                    line += ' — huge class · prefer method reads'
                if docs and row.get('doc'):
                    line += ' — ' + row.get('doc')
                lines.append(line.rstrip())
        else:
            lines.append('Target summary:')
            for key in sorted(kind_counts):
                lines.append('- %s: %d' % (key, kind_counts[key]))

            lines.append('')
            lines.append('Target highlights:')
            emitted = 0
            for row in ranked_targets:
                if emitted >= min(18, limit):
                    break
                name = row.get('name') or ''
                target_ref = row.get('target') or ''
                if not target_ref:
                    continue
                line = '- %-10s %-30s %-9s %s' % (
                    row.get('kind') or '',
                    name[:30],
                    row.get('range') or '',
                    target_ref,
                )
                if (
                    row.get('kind') == 'class'
                    and str(row.get('target') or '').endswith('.*')
                    and row_span(row) >= 300
                ):
                    line += ' — huge class · prefer method reads'
                if docs and row.get('doc'):
                    line += ' — ' + row.get('doc')
                lines.append(line.rstrip())
                emitted += 1

            if len(targets) > emitted:
                lines.append('- ... %d more target(s)' % (len(targets) - emitted))
            lines.append('- Use MODE: targets for full target listing.')

    # --- Suggested reads (suppress when MODE: imports) ---
    if show_targets:
        suggestions = []
        seen_suggestions = set()

        for row in ranked_targets:
            target_ref = row.get('target')
            if not target_ref or target_ref in seen_suggestions:
                continue

            kind = row.get('kind') or ''
            name = row.get('name') or ''
            span = row_span(row)

            # Avoid massive class dumps in default suggestions.
            if kind == 'class' and span > 300 and not full_targets:
                continue
            if target_ref.endswith('.*') and span > 300 and not full_targets:
                continue

            seen_suggestions.add(target_ref)
            suggestions.append(target_ref)

            if len(suggestions) >= (8 if large_file else 5):
                break

        lines.append('')
        lines.append('Suggested next reads:')
        if suggestions:
            for target_ref in suggestions:
                lines.append('- READ %s' % target_ref)
        else:
            lines.append('- READ %s' % rel)

    # --- Suggested dependency maps (suppress when MODE: targets) ---
    if show_imports and local_paths:
        # Filter self from dependency suggestions.
        dep_paths = [p for p in local_paths if p != rel]
        if dep_paths:
            lines.append('')
            lines.append('Suggested dependency maps:')
            for path in dep_paths[:min(12, limit)]:
                lines.append('- MAP %s' % path)
            if len(dep_paths) > min(12, limit):
                lines.append('- ... %d more local dependency map(s)' % (len(dep_paths) - min(12, limit)))

    return lines


def _render_directory(root, abs_path, target, mode, depth, docs, limit):
    rel = _rel(root, abs_path)

    noise_dirs = set([
        '.git', '__pycache__', '.pytest_cache', '.mypy_cache',
        'patch_runs', 'script_snapshots', 'build', 'dist',
        'node_modules', '.venv', 'venv',
        'site-packages', 'site-packages-2', 'site-packages-3',
        'artifacts', 'snapshots',
    ])
    noise_files = set([
        '.DS_Store', 'crash_log.txt', 'crash_trail.json',
    ])

    def visible_walk(base, max_depth):
        base = os.path.abspath(base)
        for dirpath, dirnames, filenames in os.walk(base):
            level = max(0, dirpath.rstrip(os.sep).count(os.sep) - base.rstrip(os.sep).count(os.sep))
            if level > max_depth:
                dirnames[:] = []
                continue

            dirnames[:] = sorted([d for d in dirnames if d not in noise_dirs and not d.startswith('.')])
            filenames = sorted([f for f in filenames if f not in noise_files and not f.startswith('.')])
            yield dirpath, dirnames, filenames

            if level >= max_depth:
                dirnames[:] = []

    total_files = 0
    total_dirs = 0
    py_files = []
    skipped_noise = []

    for dirpath, dirnames, filenames in visible_walk(abs_path, depth):
        total_dirs += len(dirnames)
        total_files += len(filenames)
        for name in filenames:
            full = os.path.join(dirpath, name)
            if _is_python(full):
                py_files.append(full)

    try:
        for name in sorted(os.listdir(abs_path)):
            if name in noise_dirs or name in noise_files:
                skipped_noise.append(name)
    except Exception:
        skipped_noise = []

    lines = [
        'MAP %s' % target,
        'TYPE=directory',
        'path: ' + rel,
        'depth: %d' % depth,
        'view: source-focused',
        'files: %d' % total_files,
        'dirs: %d' % total_dirs,
        'python files: %d' % len(py_files),
    ]

    if skipped_noise:
        lines.append('noise skipped: ' + ', '.join(skipped_noise[:8]))

    readme = _find_readme(abs_path)
    project_hints = _read_project_hints(root, readme) if readme and docs else {'entrypoints': []}

    ranked_entrypoints = _rank_entrypoints(
        root,
        abs_path,
        py_files,
        (
            readme
            if docs
            else None
        ),
        project_hints,
    )

    entrypoint_paths = set(
        row.get('path')
        for row in ranked_entrypoints
        if row.get('path')
    )

    if readme:
        lines.append('')
        lines.append('README:')
        hint = _read_doc_hint(readme) if docs else ''
        if hint:
            lines.append('- %s — %s' % (_rel(root, readme), hint))
        else:
            lines.append('- %s' % _rel(root, readme))

    if project_hints.get('entrypoints'):
        lines.append('')
        lines.append('Project hints:')
        for rel_entry in project_hints.get('entrypoints')[:5]:
            lines.append('- entrypoint: %s' % rel_entry)

    if ranked_entrypoints:
        lines.append('')
        lines.append('Likely entrypoints:')

        entrypoint_cap = min(
            10,
            limit,
        )

        for row in ranked_entrypoints[
            :entrypoint_cap
        ]:
            reasons = ', '.join(
                row.get(
                    'reasons'
                )
                or []
            )

            if reasons:
                lines.append(
                    '- %s — %s'
                    % (
                        row.get(
                            'rel'
                        ),
                        reasons,
                    )
                )
            else:
                lines.append(
                    '- '
                    + row.get(
                        'rel'
                    )
                )

        overflow = (
            len(
                ranked_entrypoints
            )
            - entrypoint_cap
        )

        if overflow > 0:
            lines.append(
                '- ... %d more candidate(s)'
                % overflow
            )

    lines.append('')
    lines.append('Structure:')

    emitted = 0
    for dirpath, dirnames, filenames in visible_walk(abs_path, depth):
        indent_level = max(0, dirpath.rstrip(os.sep).count(os.sep) - abs_path.rstrip(os.sep).count(os.sep))
        pad = '  ' * indent_level

        if dirpath != abs_path:
            lines.append('%s%s/' % (pad, os.path.basename(dirpath)))

        child_pad = '  ' * (indent_level + 1)

        for dirname in dirnames:
            if emitted >= limit:
                break
            lines.append('%s%s/' % (child_pad, dirname))
            emitted += 1

        for filename in filenames:
            if emitted >= limit:
                break
            full = os.path.join(dirpath, filename)
            marker = ''
            if filename in _README_NAMES or filename.lower().startswith('readme'):
                marker = ' · readme'
            elif _is_python(full):
                if full in entrypoint_paths:
                    marker = ' · py · entry'
                else:
                    marker = ' · py'
            lines.append('%s%s%s' % (child_pad, filename, marker))
            emitted += 1

        if emitted >= limit:
            lines.append('... limit reached')
            break

    lines.append('')
    lines.append('Suggested next steps:')

    if readme:
        lines.append('- READ %s' % _rel(root, readme))

    suggested = []
    seen_suggested = set()

    def add_suggestion(rel_path):
        rel_path = str(rel_path or '').strip()
        if not rel_path or rel_path in seen_suggested:
            return
        seen_suggested.add(rel_path)
        suggested.append(rel_path)

    # One entrypoint ranking drives the first source suggestions.
    #
    # Keep this section intentionally small. MAP already reports the total
    # Python-file count and structure above; hundreds of hidden suggestions
    # add packet noise without helping the next decision.
    suggestion_cap = min(
        8,
        limit,
    )

    for row in ranked_entrypoints:
        if len(
            suggested
        ) >= suggestion_cap:
            break

        add_suggestion(
            row.get(
                'rel'
            )
        )

    if len(
        suggested
    ) < suggestion_cap:
        ranked_py = sorted(
            py_files,
            key=lambda path: (
                _source_suggestion_key(
                    abs_path,
                    path,
                )
            ),
        )

        for path in ranked_py:
            if len(
                suggested
            ) >= suggestion_cap:
                break

            add_suggestion(
                _rel(
                    root,
                    path,
                )
            )

    for rel_path in suggested:
        lines.append(
            '- MAP %s'
            % rel_path
        )

    if not readme and not ranked_entrypoints and not py_files:
        lines.append('- READ %s' % rel)

    return lines


def execute(ctx, parsed_op, result):
    raw_target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    mode = _mode(parsed_op)
    depth = _as_int(directives.get('DEPTH'), 1)
    depth = max(0, min(depth, 5))
    limit = _as_int(directives.get('LIMIT'), 80)
    limit = max(1, limit)
    docs = _truthy(directives.get('DOCS'), default=True)

    root, abs_path, err = safe_target(ctx, raw_target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    if not os.path.exists(abs_path):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'Target not found: ' + raw_target
        return

    if mode == 'relationships':
        if not _is_python(abs_path):
            result['status'] = 'FAILED_INVALID_TARGET'
            result['message'] = (
                'MAP MODE: relationships currently requires a Python file.'
            )
            return

        try:
            lines = _render_python_relationships(
                root,
                abs_path,
                raw_target,
                limit,
            )
        except Exception as e:
            result['status'] = 'FAILED'
            result['message'] = (
                'Relationship map failed: %s: %s'
                % (type(e).__name__, e)
            )
            return

        kind = 'python-relationships'

    elif os.path.isdir(abs_path):
        lines = _render_directory(
            root,
            abs_path,
            raw_target,
            mode,
            depth,
            docs,
            limit,
        )
        kind = 'directory'

    elif _is_python(abs_path):
        lines = _render_python_file(
            root,
            abs_path,
            raw_target,
            mode,
            docs,
            limit,
        )
        kind = 'python-file'

    else:
        lines = _render_file_basic(
            root,
            abs_path,
            raw_target,
            docs,
        )
        kind = 'file'

    map_data = _preview_sections(lines)

    result['status'] = 'APPLIED'
    result['message'] = '%s mapped' % kind
    result['preview'] = '\n'.join(lines).rstrip()
    result['data'] = {
        'target': raw_target,
        'kind': kind,
        'mode': mode,
        'depth': depth,
        'limit': limit,
        'docs': docs,
        'map_target': map_data.get('map_target') or raw_target,
        'map_type': map_data.get('map_type') or kind,
        'fields': map_data.get('fields') or {},
        'sections': map_data.get('sections') or {},
        'shape': _shape_summary(map_data),
        'commands': _command_rows(map_data),
        'imports_preview': _import_rows_from_preview(map_data),
        'targets_preview': _target_rows_from_preview(map_data),
        'local_dependencies': _local_dependency_rows(map_data),
        'agent': _agent_data(raw_target, kind, map_data),
    }
