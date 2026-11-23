# -*- coding: utf-8 -*-
"""
RUN PATHS (project folders on sys.path for one run) and OUTPUT: ends
(first and last lines of a passing run).

Feedback 2026-11-23: scratch scripts repeated sys.path boilerplate to
import a project package; tail hid the summary lines at the top.
"""

import unittest

from forge_case import ForgeCase, bundle


def preview_of(run, index=0):
    return str((run.get('results') or [])[index].get('preview') or '')


def status_of(run, index=0):
    return (run.get('results') or [])[index].get('status')


TWENTY_LINES = 'for n in range(1, 21):\n    print("line %02d" % n)\n'


class RunOutputEnds(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('twenty.py', TWENTY_LINES)
        self.put('twenty_then_fail.py', TWENTY_LINES + 'raise SystemExit(3)\n')

    def test_ends_keeps_first_and_last_lines(self):
        preview = preview_of(self.run_bundle(bundle('RUN twenty.py', 'OUTPUT: ends 3')))
        for kept in ('line 01', 'line 03', 'line 18', 'line 20'):
            self.assertIn(kept, preview)
        for dropped in ('line 04', 'line 17'):
            self.assertNotIn(dropped, preview)
        self.assertIn('14 middle lines hidden', preview)

    def test_ends_without_a_count_uses_the_default(self):
        preview = preview_of(self.run_bundle(bundle('RUN twenty.py', 'OUTPUT: ends')))
        self.assertIn('line 06', preview)
        self.assertNotIn('line 07', preview)
        self.assertIn('line 15', preview)

    def test_a_failed_run_still_shows_everything(self):
        preview = preview_of(self.run_bundle(bundle('RUN twenty_then_fail.py', 'OUTPUT: ends 3')))
        self.assertIn('line 10', preview)
        self.assertNotIn('hidden', preview)


class RunPaths(ForgeCase):

    def forget_pkg(self):
        # Each test has its own temporary workspace, and RUN only evicts
        # modules from the current one, so a pkg imported by an earlier
        # test would otherwise still be cached.
        import sys
        sys.modules.pop('pkg', None)

    def tearDown(self):
        self.forget_pkg()
        super().tearDown()

    def setUp(self):
        super().setUp()
        self.forget_pkg()
        self.run_bundle(bundle(
            'WRITE proj/pkg/__init__.py',
            'BEGIN_BODY',
            'VALUE = 42',
            'END_BODY',
            '',
            'WRITE scratch/use_it.py',
            'BEGIN_BODY',
            'import pkg',
            'print("value", pkg.VALUE)',
            'END_BODY',
        ))

    def test_paths_makes_a_project_package_importable(self):
        run = self.run_bundle(bundle('RUN scratch/use_it.py', 'PATHS: proj'))
        self.assertEqual(status_of(run), 'APPLIED')
        self.assertIn('value 42', preview_of(run))

    def test_without_paths_the_import_fails(self):
        run = self.run_bundle(bundle('RUN scratch/use_it.py'))
        self.assertEqual(status_of(run), 'FAILED_RUNTIME')
        self.assertIn('ModuleNotFoundError', preview_of(run))

    def test_a_missing_folder_is_refused(self):
        run = self.run_bundle(bundle('RUN scratch/use_it.py', 'PATHS: nowhere'))
        self.assertEqual(status_of(run), 'FAILED_NOT_FOUND')

    def test_sys_path_is_restored_after_the_run(self):
        import sys
        before = list(sys.path)
        self.run_bundle(bundle('RUN scratch/use_it.py', 'PATHS: proj'))
        self.assertEqual(sys.path, before)


if __name__ == '__main__':
    unittest.main()