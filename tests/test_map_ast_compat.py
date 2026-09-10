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

    def test_main_guard_detection_without_legacy_ast_str(self):
        sentinel = object()
        original = getattr(ast, 'Str', sentinel)
        try:
            if hasattr(ast, 'Str'):
                delattr(ast, 'Str')
            for source in (
                "if __name__ == '__main__':\n    pass\n",
                "if '__main__' == __name__:\n    pass\n",
            ):
                node = ast.parse(source).body[0].test
                self.assertTrue(map_op._is_main_guard_test(node))
            node = ast.parse(
                "if __name__ == 'other':\n    pass\n"
            ).body[0].test
            self.assertFalse(map_op._is_main_guard_test(node))
        finally:
            if original is not sentinel:
                ast.Str = original


if __name__ == '__main__':
    unittest.main()
