# -*- coding: utf-8 -*-
"""
A directive may appear once per operation.

A repeated directive used to replace the earlier value without a word, so
the operation ran with a setting the bundle's reader could not predict.
It is now a parse error, and a parse error means nothing executes.
"""

import unittest

from forge_case import ForgeCase, bundle


class DuplicateDirectiveIsRefused(ForgeCase):

    def test_repeated_directive_fails_to_parse(self):
        self.put('notes.txt', 'one\ntwo\nthree\n')

        run = self.run_bundle(
            bundle(
                'READ notes.txt',
                'LINES: 1-1',
                'LINES: 2-3',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE')
        self.assertEqual(run.get('results') or [], [])
        self.assertIn(
            'Duplicate directive',
            ' '.join(str(error) for error in run.get('errors') or []),
        )

    def test_different_directives_still_parse(self):
        run = self.run_bundle(
            bundle(
                'MAP .',
                'DEPTH: 1',
                'LIMIT: 5',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])


if __name__ == '__main__':
    unittest.main()