# -*- coding: utf-8 -*-
"""Regression coverage for MAP across Python AST versions."""

import ast
import importlib
import unittest

import forge.packages.core_ops.map as map_package
from forge.packages.core_ops.map import op as map_op


class MapAstCompatibilityTests(unittest.TestCase):
    def test_literal_text_accepts_string_constant(self):
        node = ast.parse(
            "'Forge works'"
        ).body[0].value

        self.assertEqual(
            map_op._literal_text(node),
            'Forge works',
        )

    def test_literal_text_rejects_non_string_constant(self):
        node = ast.parse(
            '314'
        ).body[0].value

        self.assertIsNone(
            map_op._literal_text(node)
        )

    def test_map_package_restores_missing_legacy_ast_str_name(self):
        sentinel = object()
        original = getattr(
            ast,
            'Str',
            sentinel,
        )

        try:
            if hasattr(ast, 'Str'):
                delattr(ast, 'Str')

            importlib.reload(
                map_package
            )

            self.assertTrue(
                hasattr(ast, 'Str')
            )

            node = ast.parse(
                "if __name__ == '__main__':\n    pass\n"
            ).body[0].test

            self.assertTrue(
                map_op._is_main_guard_test(node)
            )

        finally:
            if original is sentinel:
                try:
                    delattr(ast, 'Str')
                except AttributeError:
                    pass
            else:
                ast.Str = original

            importlib.reload(
                map_package
            )


if __name__ == '__main__':
    unittest.main()
