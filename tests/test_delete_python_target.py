# -*- coding: utf-8 -*-
"""
DELETE path::Target removes one whole Python definition.

READ, REPLACE and INSERT all take Python targets, so DELETE refusing them
sent the model to an exact OLD block of the whole definition, which fails
on the first character that differs. The target form removes the
definition's own lines (decorators included) and the blank lines directly
above it, and never leaves a file that cannot compile.
"""

import unittest

from forge_case import ForgeCase, bundle


MODULE = '\n'.join([
    'import os',
    '',
    '',
    'LIMIT = 3',
    '',
    '',
    'def first():',
    '    return 1',
    '',
    '',
    'def second():',
    '    return 2',
    '',
    '',
    'class Board:',
    '',
    '    def reset(self):',
    '        return 0',
    '',
    '    @property',
    '    def score(self):',
    '        return 1',
    '',
])


class DeletePythonTarget(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('app.py', MODULE)

    def test_function_goes_with_the_blank_lines_above_it(self):
        run = self.run_bundle('DELETE app.py::first')

        self.assertEqual(self.statuses(run), ['APPLIED'])
        text = self.get('app.py')
        self.assertNotIn('def first', text)
        self.assertIn('LIMIT = 3\n\n\ndef second():', text)

    def test_decorated_method_takes_its_decorator(self):
        run = self.run_bundle('DELETE app.py::Board.score')

        self.assertEqual(self.statuses(run), ['APPLIED'])
        text = self.get('app.py')
        self.assertNotIn('score', text)
        self.assertNotIn('@property', text)
        self.assertTrue(text.endswith('        return 0\n'))

    def test_assignment_target(self):
        run = self.run_bundle('DELETE app.py::@LIMIT')

        self.assertEqual(self.statuses(run), ['APPLIED'])
        text = self.get('app.py')
        self.assertNotIn('LIMIT', text)
        self.assertTrue(text.startswith('import os\n\n\ndef first():'))

    def test_missing_target_is_not_found(self):
        run = self.run_bundle('DELETE app.py::nowhere')

        self.assertEqual(self.statuses(run), ['FAILED_NOT_FOUND'])
        self.assertEqual(self.get('app.py'), MODULE)

    def test_deleting_the_only_statement_in_a_body_is_refused(self):
        solo = 'class Solo:\n    def only(self):\n        return 1\n'
        self.put('solo.py', solo)

        run = self.run_bundle('DELETE solo.py::Solo.only')

        self.assertEqual(self.statuses(run), ['FAILED_COMPILE'])
        self.assertEqual(self.get('solo.py'), solo)

    def test_definition_sharing_a_line_is_refused(self):
        pair = 'A = 1; B = 2\n'
        self.put('pair.py', pair)

        run = self.run_bundle('DELETE pair.py::@A')

        self.assertEqual(self.statuses(run), ['FAILED_UNSUPPORTED'])
        self.assertEqual(self.get('pair.py'), pair)

    def test_target_with_lines_is_refused_before_anything_runs(self):
        run = self.run_bundle(
            bundle(
                'DELETE app.py::first',
                'LINES: 1-2',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertEqual(run.get('results') or [], [])
        self.assertEqual(self.get('app.py'), MODULE)


if __name__ == '__main__':
    unittest.main()