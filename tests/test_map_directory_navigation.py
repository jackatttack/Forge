# -*- coding: utf-8 -*-
"""Directory MAP navigation and bounded traversal regressions."""

import os
import shutil
from unittest import mock

from forge_case import ForgeCase, bundle
from forge.packages.core_ops.map import op as map_op


class DirectoryMapTests(ForgeCase):
    def tearDown(self):
        shutil.rmtree(self.project_root)

    def folder(self, path):
        os.makedirs(os.path.join(self.project_root, path), exist_ok=True)

    def preview(self, depth=1, limit=80):
        run = self.run_bundle(bundle(
            'MAP .', 'DEPTH: %d' % depth, 'LIMIT: %d' % limit,
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        result = run['results'][0]
        self.assertEqual(result['data']['kind'], 'directory')
        self.assertTrue(result['data']['sections']['Structure'])
        self.assertEqual(result['data']['commands'], [])
        return result['preview'], result['data']

    def test_hierarchy_has_no_duplicate_directories(self):
        self.folder('alpha/nested')
        self.folder('beta')
        self.put('alpha/one.py', 'print(1)')
        self.put('alpha/nested/two.txt', 'two')
        text, data = self.preview(depth=2)
        rows = text.splitlines()
        self.assertEqual(rows.count('  alpha/'), 1)
        self.assertEqual(rows.count('    nested/'), 1)
        self.assertIn('      two.txt', rows)
        self.assertIn('    one.py', rows)
        self.assertNotIn('Likely entrypoints:', text)
        self.assertNotIn('Suggested next steps:', text)
        self.assertEqual(data['shape']['files'], 2)
        self.assertEqual(data['shape']['dirs'], 3)

    def test_large_first_folder_does_not_starve_later_folder(self):
        self.folder('alpha')
        self.folder('zeta')
        for index in range(20):
            self.put('alpha/a%02d.txt' % index, '')
        self.put('zeta/important.txt', '')
        text, data = self.preview(limit=4)
        self.assertIn('    important.txt', text.splitlines())
        self.assertIn('+19 more; limit', text)
        self.assertEqual(data['shape']['files'] + data['shape']['dirs'], 4)

    def test_depth_zero_shows_root_and_marks_collapsed_contents(self):
        self.folder('alpha/nested')
        self.put('alpha/one.txt', '')
        text, data = self.preview(depth=0)
        self.assertIn('alpha/  [+2 more; depth]', text)
        self.assertNotIn('nested/', text)
        self.assertEqual(data['shape']['dirs'], 1)

    def test_exact_limit_does_not_claim_truncation(self):
        self.put('one.txt', '')
        text, data = self.preview(limit=1)
        self.assertNotIn('; limit', text)

    def test_root_overflow_is_explicit(self):
        self.put('one.txt', '')
        self.put('two.txt', '')
        text, data = self.preview(limit=1)
        self.assertIn('+1 more; limit', text)
        self.assertEqual(data['shape']['files'], 1)

    def test_filters_are_counted_at_their_parent(self):
        self.folder('alpha/__pycache__')
        self.folder('node_modules')
        self.put('alpha/.hidden', '')
        self.put('alpha/visible.txt', '')
        text, data = self.preview()
        self.assertIn('./  [2 filtered]', text)
        self.assertIn('alpha/  [2 filtered]', text)
        self.assertNotIn('__pycache__', text)
        self.assertIn('visible.txt', text)

    def test_directory_mapping_does_not_read_or_rank_source(self):
        self.put('main.py', 'raise RuntimeError("never execute")')
        with mock.patch.object(
            map_op, '_rank_entrypoints', side_effect=AssertionError('ranking'),
        ), mock.patch.object(
            map_op, 'read_text', side_effect=AssertionError('source read'),
        ):
            text, data = self.preview()
        self.assertIn('main.py', text)

    def test_unreadable_directory_is_reported(self):
        with mock.patch.object(
            map_op.os, 'scandir', side_effect=PermissionError('blocked'),
        ):
            text, data = self.preview()
        self.assertIn('unreadable: PermissionError', text)
        self.assertNotIn('[empty]', text)