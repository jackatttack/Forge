# -*- coding: utf-8 -*-
"""
How Forge behaves after an operation fails.

These tests pin CURRENT behaviour so the planned policy refactor has a
baseline to break against. Where current behaviour is believed to be
wrong, the test still asserts what Forge does today and says so. Those
tests are meant to be inverted deliberately when the behaviour changes.
"""

import unittest

from forge_case import ForgeCase, bundle


class MutationStopsAfterFailure(ForgeCase):

    def test_failed_write_skips_a_later_write(self):
        """A refused overwrite must stop later mutating ops."""
        self.put('notes.txt', 'original\n')

        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                'replacement',
                'END_BODY',
                '',
                'WRITE second.txt',
                'BEGIN_BODY',
                'should not be created',
                'END_BODY',
            )
        )

        statuses = self.statuses(run)

        self.assertNotEqual(statuses[0], 'APPLIED')
        self.assertEqual(statuses[1], 'SKIPPED_AFTER_FAILURE')
        self.assertFalse(self.exists('second.txt'))
        self.assertEqual(self.get('notes.txt'), 'original\n')

    def test_failed_write_still_allows_read(self):
        """Read-only diagnostics must survive an earlier failure."""
        self.put('notes.txt', 'original\n')

        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                'replacement',
                'END_BODY',
                '',
                'READ notes.txt',
            )
        )

        self.assertEqual(self.statuses(run)[1], 'APPLIED')

    def test_run_does_not_execute_after_a_failure(self):
        """
        RUN must not execute after an earlier mutating failure.

        RUN compiles and executes arbitrary project Python, so allowing
        it through the stop would defeat the purpose of stopping. It was
        previously in the engine's continue-after-failure list; this
        test exists to keep it out.
        """
        self.put('notes.txt', 'original\n')
        self.put(
            'sentinel.py',
            'open("ran.txt", "w").write("executed")\n',
        )

        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                'replacement',
                'END_BODY',
                '',
                'RUN sentinel.py',
            )
        )

        self.assertEqual(self.statuses(run)[1], 'SKIPPED_AFTER_FAILURE')
        self.assertFalse(self.exists('ran.txt'))


class ParseFailuresExecuteNothing(ForgeCase):

    def test_a_parse_error_prevents_every_operation(self):
        """An unparseable bundle must not execute its valid operations."""
        run = self.run_bundle(
            bundle(
                'WRITE created.txt',
                'BEGIN_BODY',
                'content',
                'END_BODY',
                '',
                'NOSUCHOP whatever',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertEqual(run.get('results') or [], [])
        self.assertFalse(self.exists('created.txt'))


if __name__ == '__main__':
    unittest.main(verbosity=2)