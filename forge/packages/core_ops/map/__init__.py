# -*- coding: utf-8 -*-
"""MAP operation package compatibility boundary."""

import ast


# PythonIDE currently ships Python 3.14.6 without the deprecated ``ast.Str``
# compatibility name. MAP still has one guarded legacy check for that symbol
# before falling back to ``node.value``. Supplying a marker class here keeps
# older Forge code importable without changing the AST objects produced by
# modern Python: parsed string literals continue down the ``node.value`` path.
#
# This shim is intentionally local to the MAP package and only runs when the
# standard-library alias is genuinely absent.
if not hasattr(ast, 'Str'):
    class _ForgeLegacyAstStr(object):
        pass

    ast.Str = _ForgeLegacyAstStr
