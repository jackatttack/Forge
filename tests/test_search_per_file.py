# -*- coding: utf-8 -*-
"""
One noisy file cannot take every hit of a directory search.

Each file shows at most a quarter of LIMIT (minimum 3) in a directory
search. Hidden hits are counted. Single-file searches and EXPECT_HITS see
every hit. ACTIVE_ONLY skips backup folders.
"""

import os
import unittest

from forge_case import ForgeCase, bundle


class PerFileCap(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('noisy.txt', 'needle\n' * 20)
        self.put('a.py', 'needle = 1\n')
        self.put('b.py', 'x = "needle"\n')

    def preview_of(self, *lines):
        run = self.run_bundle(bundle(*lines))
        return run, run['results'][0].get('preview') or ''

    def test_directory_search_reaches_every_file(self):
        run, preview = self.preview_of('SEARCH . FOR needle', 'LIMIT: 10')
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertIn('a.py', preview)
        self.assertIn('b.py', preview)
        self.assertIn('noisy.txt  (+17 more hits here', preview)
        self.assertIn('per-file cap 3: 17 more hits in 1 file not shown', preview)

    def test_single_file_search_is_uncapped(self):
        run, preview = self.preview_of('SEARCH noisy.txt FOR needle', 'LIMIT: 10')
        self.assertEqual(len(run['results'][0]['data']['hits']), 10)
        self.assertNotIn('per-file cap', preview)

    def test_expect_hits_counts_every_hit(self):
        run, _ = self.preview_of(
            'SEARCH . FOR needle', 'LIMIT: 50', 'EXPECT_HITS: 22')
        self.assertEqual(run['results'][0]['status'], 'APPLIED')


class ActiveOnlySkipsBackups(ForgeCase):

    def test_backup_folder_is_skipped(self):
        self.put('live.py', 'needle = 1\n')
        os.makedirs(os.path.join(self.project_root, 'runtime_backups'))
        self.put('runtime_backups/old.py', 'needle = 0\n')
        run = self.run_bundle(bundle(
            'SEARCH . FOR needle', 'ACTIVE_ONLY: yes'))
        files = [hit['file'] for hit in run['results'][0]['data']['hits']]
        self.assertEqual(files, ['live.py'])


if __name__ == '__main__':
    unittest.main()