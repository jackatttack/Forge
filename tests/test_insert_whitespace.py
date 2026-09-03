# -*- coding: utf-8 -*-
"""
Whitespace handling in INSERT.

Plain-file insertion writes the body exactly as given. AST insertion
re-aligns the body to its destination in the syntax tree.

The distinction matters because these are different jobs. Inserting a
function into a class needs the body re-indented to sit inside that
class. Inserting a step into a YAML workflow needs the body left alone,
because its indentation IS its meaning.

Plain-file insertion previously dedented the body and applied no indent
in its place, so an indented block lost its leading whitespace and the
operation still reported APPLIED. These tests pin the verbatim contract.
"""

import unittest

from forge_case import ForgeCase, bundle


class PlainFileBodyIsVerbatim(ForgeCase):

    def test_uniform_indentation_is_preserved(self):
        self.put('config.yml', 'jobs:\n  build:\n')

        run = self.run_bundle(
            bundle(
                'INSERT config.yml',
                'LINE: 2',
                'POSITION: after',
                'BEGIN_BODY',
                '    steps:',
                '      - run: echo hi',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(
            self.get('config.yml'),
            'jobs:\n  build:\n    steps:\n      - run: echo hi\n',
        )

    def test_relative_indentation_is_preserved(self):
        self.put('notes.txt', 'first\nlast\n')

        run = self.run_bundle(
            bundle(
                'INSERT notes.txt',
                'LINE: 1',
                'POSITION: after',
                'BEGIN_BODY',
                '    outer',
                '        inner',
                '    outer again',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])

        lines = self.get('notes.txt').splitlines()

        self.assertEqual(lines[1], '    outer')
        self.assertEqual(lines[2], '        inner')
        self.assertEqual(lines[3], '    outer again')

    def test_blank_lines_inside_the_body_survive(self):
        self.put('notes.txt', 'first\nlast\n')

        run = self.run_bundle(
            bundle(
                'INSERT notes.txt',
                'LINE: 1',
                'POSITION: after',
                'BEGIN_BODY',
                '  two spaces',
                '',
                '  after a blank',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])

        lines = self.get('notes.txt').splitlines()

        self.assertEqual(lines[1], '  two spaces')
        self.assertEqual(lines[2], '')
        self.assertEqual(lines[3], '  after a blank')

    def test_unindented_body_is_unaffected(self):
        """The common case must not change."""
        self.put('notes.txt', 'first\nlast\n')

        run = self.run_bundle(
            bundle(
                'INSERT notes.txt',
                'LINE: 1',
                'POSITION: after',
                'BEGIN_BODY',
                'middle',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get('notes.txt'), 'first\nmiddle\nlast\n')

    def test_insert_before_first_line(self):
        self.put('notes.txt', 'first\nlast\n')

        run = self.run_bundle(
            bundle(
                'INSERT notes.txt',
                'LINE: 1',
                'POSITION: before',
                'BEGIN_BODY',
                '  header',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(
            self.get('notes.txt'),
            '  header\nfirst\nlast\n',
        )


class AstInsertionStillReindents(ForgeCase):
    """
    AST insertion must keep re-aligning bodies to their destination.

    The plain-file fix must not leak into this path: a helper written at
    column zero still has to land correctly inside a function body.
    """

    def test_body_end_insert_is_indented_into_the_function(self):
        self.put(
            'app.py',
            'def main():\n    value = 1\n    return value\n',
        )

        run = self.run_bundle(
            bundle(
                'INSERT app.py::main',
                'POSITION: end',
                'BEGIN_BODY',
                'print("done")',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])

        text = self.get('app.py')

        self.assertIn('    print("done")', text)
        self.assertNotIn('\nprint("done")', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)