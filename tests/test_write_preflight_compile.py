# -*- coding: utf-8 -*-
"""
A WRITE whose Python body cannot compile refuses the whole bundle.

The body is the complete file, so the check needs nothing from disk. It
used to run when the WRITE executed, after earlier operations had already
applied, which left a bundle half done at the broken file. Refusing at
preflight means nothing ran and the stored bundle can be repaired.
"""

import unittest

from forge_case import ForgeCase, bundle


class BrokenWriteRefusesTheWholeBundle(ForgeCase):

    def test_nothing_runs_when_a_later_write_cannot_compile(self):
        run = self.run_bundle(
            bundle(
                'WRITE good.py',
                'BEGIN_BODY',
                'VALUE = 1',
                'END_BODY',
                '',
                'WRITE bad.py',
                'BEGIN_BODY',
                'def broken(:',
                '    pass',
                'END_BODY',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE')
        self.assertEqual(run.get('results') or [], [])
        self.assertFalse(self.exists('good.py'))
        self.assertIn(
            'bad.py would not compile',
            ' '.join(str(error) for error in run.get('errors') or []),
        )

    def test_allow_broken_still_writes(self):
        run = self.run_bundle(
            bundle(
                'WRITE fixture.py',
                'ALLOW_BROKEN: yes',
                'BEGIN_BODY',
                'def broken(:',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertTrue(self.exists('fixture.py'))

    def test_other_file_types_are_not_compiled(self):
        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                'def broken(:',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])


if __name__ == '__main__':
    unittest.main()