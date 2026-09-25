# -*- coding: utf-8 -*-
"""
Symbol index for Python directories.

One line per Python file, naming its top-level classes and functions, and
optionally the literal values given to a named key (for example every
GeneratorInfo(id=...) in a package).

Used by MAP MODE: symbols. It reads and parses every selected .py file, so
it is opt-in rather than part of the default directory map, which never
reads source.
"""

import ast
import fnmatch
import os
import textwrap

from forge.core.file_safety import read_text


# ---- Editable presentation settings -----------------------------------------

# Index lines wrap at this width; continuation lines are indented.
LINE_WIDTH = 100

# Key values longer than this are shortened so one odd value cannot flood
# the index.
MAX_VALUE_CHARS = 40


def collect_python_files(abs_path, skip_dir_names, globs=()):
    """
    Return (paths, stats) for the .py files under abs_path, sorted by path.

    Directories named in skip_dir_names, and dot-directories, are pruned.
    globs are file-name patterns (case-insensitive); when given, only .py
    files whose name matches one are kept.

    stats records what was left out, so the caller can say so rather than
    leave "not found" and "never looked" indistinguishable:
      skipped_dirs     sorted names of pruned directories
      skipped_by_glob  count of .py files whose name matched no glob
      non_python       count of other files ignored
    """
    stats = {'skipped_dirs': set(), 'skipped_by_glob': 0, 'non_python': 0}

    def keep(path):
        name = os.path.basename(path)
        if not name.endswith('.py'):
            stats['non_python'] += 1
            return False
        if globs and not any(
            fnmatch.fnmatchcase(name.lower(), glob.lower()) for glob in globs
        ):
            stats['skipped_by_glob'] += 1
            return False
        return True

    paths = []

    if os.path.isfile(abs_path):
        if keep(abs_path):
            paths.append(abs_path)
    else:
        for dirpath, dirnames, filenames in os.walk(abs_path):
            kept_dirs = []
            for name in dirnames:
                if name in skip_dir_names or name.startswith('.'):
                    stats['skipped_dirs'].add(name)
                    continue
                kept_dirs.append(name)
            dirnames[:] = kept_dirs

            for name in filenames:
                if name.startswith('.'):
                    continue
                path = os.path.join(dirpath, name)
                if keep(path):
                    paths.append(path)

    stats['skipped_dirs'] = sorted(stats['skipped_dirs'])
    return sorted(paths), stats


def summarise_file(abs_file, key=None):
    """
    Parse one Python file and return what the index shows for it.

    Returns a dict:
      classes     top-level class names, in source order
      functions   top-level function names (sync and async), in source order
      key_values  literal values given to key (see _key_values), or []
      error       '' or a short reason the file could not be summarised
    """
    summary = {'classes': [], 'functions': [], 'key_values': [], 'error': ''}

    try:
        source = read_text(abs_file)
    except Exception as e:
        summary['error'] = 'unreadable: %s' % type(e).__name__
        return summary

    try:
        tree = ast.parse(source, filename=abs_file)
    except SyntaxError as e:
        summary['error'] = 'syntax error line %s' % (e.lineno or '?')
        return summary

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            summary['classes'].append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            summary['functions'].append(node.name)

    if key:
        summary['key_values'] = _key_values(tree, key)

    return summary


def _key_values(tree, key):
    """
    Return the values given to key anywhere in the module, in source order.

    Two written forms count: assignment to the plain name (key = 'x', also
    with an annotation) and a keyword argument in any call (Info(key='x')).
    Literal values are shown as written; anything else appears as <expr>, so
    the key's presence is still visible. Repeated values are shown once.
    """
    found = []

    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == key:
            found.append((_line_of(node.value), _value_text(node.value)))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == key:
                    found.append((node.lineno, _value_text(node.value)))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == key
            and node.value is not None
        ):
            found.append((node.lineno, _value_text(node.value)))

    values = []
    for _line, text in sorted(found, key=lambda item: item[0]):
        if text not in values:
            values.append(text)
    return values


def _line_of(node):
    return int(getattr(node, 'lineno', 0) or 0)


def _value_text(node):
    """Show a literal value as Python would write it, or <expr> if not literal."""
    try:
        text = repr(ast.literal_eval(node))
    except Exception:
        return '<expr>'
    if len(text) > MAX_VALUE_CHARS:
        text = text[:MAX_VALUE_CHARS - 3] + '...'
    return text


def format_file_line(rel_path, summary, key=None):
    """
    Return the wrapped index line(s) for one file.

        mathsgen/bounds_family.py — classes: Bounds · functions: make, check · id: 'bounds'
    """
    if summary.get('error'):
        parts = [summary['error']]
    else:
        parts = []
        if summary.get('classes'):
            parts.append('classes: ' + ', '.join(summary['classes']))
        if summary.get('functions'):
            parts.append('functions: ' + ', '.join(summary['functions']))
        if key and summary.get('key_values'):
            parts.append('%s: %s' % (key, ', '.join(summary['key_values'])))
        if not parts:
            parts.append('(no top-level classes or functions)')

    text = '%s — %s' % (rel_path, ' · '.join(parts))
    return textwrap.wrap(
        text,
        width=LINE_WIDTH,
        subsequent_indent='    ',
        break_on_hyphens=False,
    ) or [text]


def skip_notes(stats):
    """Describe what the index left out and why; silent when nothing was."""
    notes = []
    if stats.get('skipped_by_glob'):
        notes.append('skipped: %d Python file%s not matching GLOB' % (
            stats['skipped_by_glob'],
            '' if stats['skipped_by_glob'] == 1 else 's',
        ))
    if stats.get('non_python'):
        notes.append('skipped: %d non-Python file%s' % (
            stats['non_python'],
            '' if stats['non_python'] == 1 else 's',
        ))
    if stats.get('skipped_dirs'):
        notes.append('skipped dirs: ' + ', '.join(stats['skipped_dirs']))
    return notes


def render_symbol_index(abs_path, target, skip_dir_names, globs=(), key=None, limit=80):
    """
    Return the preview lines for a symbol index of abs_path.

    Paths in the index are relative to the target, which the header names.
    At most limit files are summarised; the rest are counted with a hint on
    how to narrow the index.
    """
    paths, stats = collect_python_files(abs_path, skip_dir_names, globs)
    shown = paths[:limit]
    base = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)

    lines = [
        'MAP ' + target,
        'TYPE=symbol-index',
        'path: ' + target,
        'python files: %d' % len(paths),
    ]
    if globs:
        lines.append('glob: ' + ','.join(globs))
    if key:
        lines.append('key: ' + key)
    lines.extend(skip_notes(stats))
    lines.append('')
    lines.append('Symbols:')

    if not paths:
        lines.append('(no Python files)')

    for path in shown:
        rel = os.path.relpath(path, base).replace('\\', '/')
        lines.extend(format_file_line(rel, summarise_file(path, key), key))

    hidden = len(paths) - len(shown)
    if hidden:
        lines.append('')
        lines.append(
            '... %d more file%s not shown (LIMIT %d); narrow with GLOB or a smaller path'
            % (hidden, '' if hidden == 1 else 's', limit)
        )

    return lines