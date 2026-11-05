# -*- coding: utf-8 -*-
"""An unclosed block names its operation and where the end was lost.

The message must be enough to repair the stored bundle in one REPLACE:
which operation, and the swallowed operation header to close before.
"""

import unittest

from forge_case import ForgeCase, bundle


class MissingEndMarker(ForgeCase):

    def errors(self, run):
        return '\n'.join(run.get('errors') or [])

    def test_names_the_swallowed_operation(self):
        run = self.run_bundle(
            bundle(
                'WRITE a.txt',
                'BEGIN_BODY',
                'text',
                '',
                'READ a.txt',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        errors = self.errors(run)
        self.assertIn('Missing END_BODY for WRITE a.txt', errors)
        self.assertIn('just before this line', errors)
        self.assertIn('READ a.txt', errors)

    def test_names_which_of_several_operations(self):
        run = self.run_bundle(
            bundle(
                'WRITE one.txt',
                'BEGIN_BODY',
                '1',
                'END_BODY',
                '',
                'WRITE two.txt',
                'BEGIN_BODY',
                '2',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('Missing END_BODY for WRITE two.txt', self.errors(run))
        self.assertFalse(self.exists('one.txt'))

    def test_without_a_swallowed_header_says_where_to_close(self):
        run = self.run_bundle(
            bundle(
                'WRITE b.txt',
                'BEGIN_BODY',
                'text',
            )
        )

        self.assertIn("after the block's last content line", self.errors(run))

    def test_indented_header_is_not_mistaken_for_an_operation(self):
        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                '    READ example.py',
            )
        )

        errors = self.errors(run)
        self.assertNotIn('just before this line', errors)
        self.assertIn("after the block's last content line", errors)

    def test_tagged_block_does_not_guess_a_header(self):
        run = self.run_bundle(
            bundle(
                'WRITE c.txt',
                'BEGIN_BODY @raw',
                'READ x.txt',
                'END_BODY',
            )
        )

        errors = self.errors(run)
        self.assertIn('Missing END_BODY @raw for WRITE c.txt', errors)
        self.assertIn('closes only at END_BODY @raw', errors)
        self.assertNotIn('just before this line', errors)


if __name__ == '__main__':
    unittest.main()
