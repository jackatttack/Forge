# -*- coding: utf-8 -*-
"""
REPLACE must never leave a file half-edited.

A refused mutation should leave the original bytes untouched, because
the whole Forge contract depends on a failed packet meaning nothing
happened.
"""

import unittest

from forge_case import ForgeCase, bundle


class ReplaceLeavesSourceIntact(ForgeCase):

    def test_anchor_mismatch_does_not_touch_the_file(self):
        """A missing OLD block must leave the file byte-identical."""
        original = 'value = 1\n'
        self.put('config.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE config.py',
                'BEGIN_OLD',
                'value = 99',
                'END_OLD',
                'BEGIN_NEW',
                'value = 2',
                'END_NEW',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.get('config.py'), original)

    def test_compile_failure_does_not_touch_the_file(self):
        """Invalid Python must be refused before anything is written."""
        original = 'def main():\n    return True\n'
        self.put('app.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE app.py::main',
                'BEGIN_BODY',
                'def main(:',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.get('app.py'), original)

    def test_missing_target_does_not_create_a_file(self):
        """REPLACE on an absent file must not create it."""
        run = self.run_bundle(
            bundle(
                'REPLACE absent.py::main',
                'BEGIN_BODY',
                'def main():',
                '    return True',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertFalse(self.exists('absent.py'))

    def test_ast_assignment_preserves_same_line_statement(self):
        """AST replacement must not consume a neighbouring statement."""
        original = 'LEFT = 1; RIGHT = 2\n'
        self.put('config.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE config.py::@LEFT',
                'BEGIN_BODY',
                'LEFT = 99',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(
            self.get('config.py'),
            'LEFT = 99; RIGHT = 2\n',
        )

    def test_ast_assignment_preserves_trailing_comment(self):
        """AST replacement must leave syntax outside the node untouched."""
        original = 'WITH_COMMENT = 10  # preserve this comment\n'
        self.put('config.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE config.py::@WITH_COMMENT',
                'BEGIN_BODY',
                'WITH_COMMENT = 11',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(
            self.get('config.py'),
            'WITH_COMMENT = 11  # preserve this comment\n',
        )

    def test_ast_span_handles_unicode_before_target(self):
        """UTF-8 AST byte columns must be converted before string slicing."""
        original = 'π = 3; AFTER_UNICODE = 4\n'
        self.put('config.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE config.py::@AFTER_UNICODE',
                'BEGIN_BODY',
                'AFTER_UNICODE = 5',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(
            self.get('config.py'),
            'π = 3; AFTER_UNICODE = 5\n',
        )

    def test_ast_span_reindents_method_body(self):
        """Exact spans must retain the old line-range indentation behaviour."""
        original = (
            'class Demo:\n'
            '    @staticmethod\n'
            '    def value():\n'
            '        return 1\n'
        )
        self.put('app.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE app.py::Demo.value',
                'BEGIN_BODY',
                'def value():',
                '    return 2',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(
            self.get('app.py'),
            (
                'class Demo:\n'
                '    @staticmethod\n'
                '    def value():\n'
                '        return 2\n'
            ),
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)