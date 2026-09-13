# -*- coding: utf-8 -*-
"""
Shared file/path safety helpers for Forge.

Keep this small and boring. Mutating ops should use the same project-root
checks so safety behaviour is consistent across CREATE/REPLACE/DELETE/MOVE.
"""

import os


def project_root(ctx):
    """Return Forge's explicit project filesystem boundary."""
    from forge.core.environment import path_from_ctx

    return path_from_ctx(
        ctx,
        'project_root',
    )


# ---------------------------------------------------------------------------
# Named roots
#
# Forge resolves every path against exactly one root. By default that is
# project_root, unchanged. A path may instead opt in to a configured
# additional root using a "name:" prefix:
#
#     projects/app.py          -> project_root (default, unchanged)
#     icloud:tools/patcher.py  -> the root configured as "icloud"
#
# Named roots come from environment['roots'], a plain {name: absolute_path}
# mapping supplied by configuration. An unknown or unconfigured name is an
# error rather than a silent fall back to project_root, because silently
# writing to the wrong tree is the one failure this must never produce.
# ---------------------------------------------------------------------------

ROOT_SEPARATOR = ':'


def split_root_prefix(rel_path):
    """
    Split "name:relative/path" into (root_name, relative_path).

    Returns (None, rel_path) when no prefix is present, which is the
    ordinary case. A Windows-style drive letter is not a concern here
    because Forge paths are always project-relative and POSIX-shaped.
    """
    text = str(rel_path or '').strip()

    if ROOT_SEPARATOR not in text:
        return None, text

    name, _, remainder = text.partition(ROOT_SEPARATOR)
    name = name.strip()

    # A separator inside a path segment ("a/b:c") is not a root prefix.
    if not name or os.sep in name or '/' in name:
        return None, text

    return name, remainder.strip()


def named_roots(ctx):
    """Return the configured {name: absolute_path} mapping, possibly empty."""
    from forge.core.environment import from_ctx

    roots = (from_ctx(ctx) or {}).get('roots') or {}

    if not isinstance(roots, dict):
        return {}

    return roots


def resolve_root(ctx, rel_path):
    """
    Return (root, relative_path, error) for one requested path.

    Without a prefix this returns project_root and the path unchanged, so
    existing behaviour is exactly preserved.
    """
    name, remainder = split_root_prefix(rel_path)

    if name is None:
        return project_root(ctx), remainder, None

    roots = named_roots(ctx)
    target = roots.get(name)

    if not target:
        known = ', '.join(sorted(roots)) or 'none configured'
        return None, remainder, (
            'Unknown root %r (known roots: %s)' % (name, known)
        )

    if not remainder:
        return os.path.abspath(str(target)), '', None

    return os.path.abspath(str(target)), remainder, None


def resolve_under_root(root, rel_path):
    root = os.path.abspath(root)
    rel_path = str(rel_path or '').strip()
    return os.path.abspath(os.path.join(root, rel_path))


def in_root(root, path):
    root_real = os.path.realpath(os.path.abspath(root))
    path_real = os.path.realpath(os.path.abspath(path))
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def safe_target(ctx, rel_path):
    """
    Resolve a requested path to (root, absolute_path, error).

    The path may carry a "name:" root prefix. Without one it resolves
    against project_root exactly as before.
    """
    root, relative, error = resolve_root(ctx, rel_path)

    if error:
        return None, None, error

    abs_path = resolve_under_root(root, relative)

    if not in_root(root, abs_path):
        return root, abs_path, 'Path escapes project root'

    return root, abs_path, None


def read_text(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def write_text(path, text):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text or '')

class CompileBlocked(Exception):
    """Raised when a .py write is refused because the new text does not compile."""

    def __init__(self, path, lineno, msg):
        self.path = path
        self.lineno = lineno
        self.msg = msg
        super().__init__('%s line %s: %s' % (path, lineno, msg))


def checked_write(path, text):
    """
    Write text, refusing to write a .py file that does not compile.

    The compile check runs BEFORE any disk write, so a failing patch
    never touches the file. Non-.py paths write normally.
    """
    if str(path or '').endswith('.py'):
        try:
            compile(text or '', str(path), 'exec')
        except SyntaxError as e:
            raise CompileBlocked(str(path), e.lineno, e.msg)
    write_text(path, text)


def touched_file(
    rel, before, after, existed_before=True, existed_after=True, root='',
):
    """
    Describe a text-file change, including absence versus empty content.

    ``root`` is the name of the configured root the path belongs to, or
    empty for the project root. It is recorded separately rather than
    left as a prefix on ``rel`` so recovery can resolve the path against
    the tree it was actually written to.
    """
    return {
        'rel': rel,
        'root': str(root or ''),
        'before': before or '',
        'after': after or '',
        'existed_before': bool(existed_before),
        'existed_after': bool(existed_after),
        'kind': 'file',
    }


def record_touched(ctx, result, touched):
    """Append a completed change to both operation and run records."""
    result.setdefault('touched', []).append(touched)
    run = (ctx or {}).get('run')
    if run is not None:
        run.setdefault('touched_files', []).append(touched)
