# -*- coding: utf-8 -*-
"""
Shared file/path safety helpers for Forge.

Keep this small and boring. Mutating ops should use the same project-root
checks so safety behaviour is consistent across CREATE/REPLACE/DELETE/MOVE.
"""

import os


def project_root(ctx):
    """Return Forge's explicit project filesystem boundary."""
    from forge_core.environment import path_from_ctx

    return path_from_ctx(
        ctx,
        'project_root',
    )


def resolve_under_root(root, rel_path):
    root = os.path.abspath(root)
    rel_path = str(rel_path or '').strip()
    return os.path.abspath(os.path.join(root, rel_path))


def in_root(root, path):
    root_real = os.path.realpath(os.path.abspath(root))
    path_real = os.path.realpath(os.path.abspath(path))
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def safe_target(ctx, rel_path):
    root = project_root(ctx)
    abs_path = resolve_under_root(root, rel_path)
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


def touched_file(rel, before, after, existed_before=True):
    return {
        'rel': rel,
        'before': before or '',
        'after': after or '',
        'existed_before': bool(existed_before),
        'kind': 'file',
    }


def record_touched(ctx, result, touched):
    result['touched'] = [touched]
    run = (ctx or {}).get('run') or {}
    run.setdefault('touched_files', []).append(touched)
