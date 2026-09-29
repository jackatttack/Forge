# -*- coding: utf-8 -*-
"""
Runtime failures report what went wrong, never FAILED_PARSE.

FAILED_PARSE promises that nothing in the bundle ran. A problem that only
shows up against the file as it is now (lines past the end, a missing or
repeated OLD block) happens after earlier ops may have applied, so it gets
a runtime status and the run as a whole reports FAILED.
"""

import unittest

from forge_case import ForgeCase, bundle


class ReplaceRuntimeStatuses(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'same\nmiddle\nsame\n')

    def status_of(self, *lines):
        run = self.run_bundle(bundle(*lines))
        self.assertEqual(run.get('status'), 'FAILED')
        return run['results'][0]['status']

    def test_lines_past_the_end(self):
        status = self.status_of(
            'REPLACE notes.txt', 'LINES: 50-60',
            'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(status, 'FAILED_NOT_FOUND')

    def test_occurrence_past_the_matches(self):
        status = self.status_of(
            'REPLACE notes.txt', 'OCCURRENCE: 3',
            'BEGIN_OLD', 'same', 'END_OLD', 'BEGIN_NEW', 'new', 'END_NEW')
        self.assertEqual(status, 'FAILED_NOT_FOUND')

    def test_repeated_old_without_selection(self):
        status = self.status_of(
            'REPLACE notes.txt',
            'BEGIN_OLD', 'same', 'END_OLD', 'BEGIN_NEW', 'new', 'END_NEW')
        self.assertEqual(status, 'FAILED_AMBIGUOUS')
        self.assertEqual(self.get('notes.txt'), 'same\nmiddle\nsame\n')


class DeleteRuntimeStatuses(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'same\nmiddle\nsame\n')

    def status_of(self, *lines):
        run = self.run_bundle(bundle(*lines))
        self.assertEqual(run.get('status'), 'FAILED')
        return run['results'][0]['status']

    def test_lines_past_the_end(self):
        status = self.status_of('DELETE notes.txt', 'LINES: 50-60')
        self.assertEqual(status, 'FAILED_NOT_FOUND')

    def test_occurrence_past_the_matches(self):
        status = self.status_of(
            'DELETE notes.txt', 'OCCURRENCE: 3',
            'BEGIN_OLD', 'same', 'END_OLD')
        self.assertEqual(status, 'FAILED_NOT_FOUND')

    def test_repeated_old_without_selection(self):
        status = self.status_of(
            'DELETE notes.txt', 'BEGIN_OLD', 'same', 'END_OLD')
        self.assertEqual(status, 'FAILED_AMBIGUOUS')
        self.assertEqual(self.get('notes.txt'), 'same\nmiddle\nsame\n')


class RuntimeFailureAfterAppliedWork(ForgeCase):

    def test_earlier_op_applies_and_run_reports_failed(self):
        """The contrast with FAILED_PARSE: earlier work did happen."""
        self.put('notes.txt', 'one\n')
        run = self.run_bundle(bundle(
            'WRITE created.txt',
            'BEGIN_BODY',
            'content',
            'END_BODY',
            '',
            'REPLACE notes.txt',
            'LINES: 50-60',
            'BEGIN_BODY',
            'new',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'FAILED')
        self.assertTrue(self.exists('created.txt'))
        self.assertEqual(run['results'][1]['status'], 'FAILED_NOT_FOUND')


if __name__ == '__main__':
    unittest.main()