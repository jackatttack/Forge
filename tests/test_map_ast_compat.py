# -*- coding: utf-8 -*-
"""Regression coverage for MAP across Python AST versions."""

import ast
import unittest

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


if __name__ == '__main__':
    unittest.main()
