"""
MAP folds data folders (cache, thumbs, previews, backups) into the
"filtered" note, unless the map is of a path inside one.

Role: check · Part of: forge/tests · Entry

Feedback 2026-11-23: MAP projects/papers at DEPTH 2 listed 50 cached
thumbnails.
"""

import unittest

from forge_case import ForgeCase, bundle


def preview_of(run, index=0):
    return str((run.get('results') or [])[index].get('preview') or '')


class MapFoldsDataFolders(ForgeCase):

    def setUp(self):
        super().setUp()
        # put() does not create folders; WRITE does.
        self.run_bundle(bundle(
            'WRITE proj/main.py',
            'BEGIN_BODY',
            'x = 1',
            'END_BODY',
            '',
            'WRITE proj/cache/thumbs/page_one.jpg',
            'BEGIN_BODY',
            'not really a jpeg',
            'END_BODY',
        ))

    def test_cache_folders_are_folded(self):
        preview = preview_of(self.run_bundle(bundle('MAP proj', 'DEPTH: 3')))
        self.assertIn('main.py', preview)
        self.assertIn('filtered', preview)
        self.assertNotIn('page_one.jpg', preview)

    def test_mapping_inside_a_data_folder_shows_everything(self):
        preview = preview_of(self.run_bundle(bundle('MAP proj/cache', 'DEPTH: 3')))
        self.assertIn('page_one.jpg', preview)


if __name__ == '__main__':
    unittest.main()