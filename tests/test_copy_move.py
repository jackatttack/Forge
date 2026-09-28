# -*- coding: utf-8 -*-
"""
COPY and MOVE: files and directory trees, across roots, fully recorded.

These tests pin the behaviour the help promises: a transfer is planned in
full and refused before writing if anything is wrong, every changed file is
recorded so REVERT undoes it, and MOVE never removes a source before every
copy is verified.
"""

import json
import os
import shutil
import tempfile
import unittest

from forge_case import bundle

import forge


class TransferCase(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.mkdtemp(prefix='forge-transfer-')
        self.addCleanup(shutil.rmtree, self.temporary, True)

        self.project_root = os.path.join(self.temporary, 'project')
        self.other_root = os.path.join(self.temporary, 'elsewhere')
        self.forge_home = os.path.join(self.temporary, '.forge')

        for folder in (self.project_root, self.other_root, self.forge_home):
            os.makedirs(folder)

        with open(
            os.path.join(self.forge_home, 'forge.json'), 'w', encoding='utf-8',
        ) as handle:
            json.dump(
                {'config_version': 1, 'roots': {'other': self.other_root}},
                handle,
            )

    # --- helpers -------------------------------------------------------------

    def run_bundle(self, *lines):
        return forge.run_text(
            bundle(*lines),
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=True,
        )

    def last(self, run):
        return run['results'][-1]

    def put(self, root, relative, content):
        path = os.path.join(root, relative)
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        if isinstance(content, bytes):
            with open(path, 'wb') as handle:
                handle.write(content)
        else:
            with open(path, 'w', encoding='utf-8', newline='') as handle:
                handle.write(content)

    def text(self, root, relative):
        with open(os.path.join(root, relative), 'rb') as handle:
            return handle.read().decode('utf-8')

    def exists(self, root, relative):
        return os.path.exists(os.path.join(root, relative))

    def make_source_tree(self):
        self.put(self.project_root, 'src/a.py', 'print("a")\n')
        self.put(self.project_root, 'src/sub/b.md', '# b\r\nwindows line\r\n')
        self.put(self.project_root, 'src/__pycache__/a.cpython.pyc', b'\x00\xff')
        self.put(self.project_root, 'src/.DS_Store', b'\x00\x01\xfe')

    def revert(self, run):
        return self.run_bundle('REVERT ' + run['stamp'])


class CopyDirectories(TransferCase):

    def test_copies_a_tree_across_roots_and_skips_default_excludes(self):
        self.make_source_tree()
        run = self.run_bundle('COPY src', 'TO: other:dest')

        result = self.last(run)
        self.assertEqual(result['status'], 'APPLIED', result.get('message'))
        self.assertEqual(self.text(self.other_root, 'dest/a.py'), 'print("a")\n')
        self.assertEqual(
            self.text(self.other_root, 'dest/sub/b.md'),
            '# b\r\nwindows line\r\n',
        )
        self.assertFalse(self.exists(self.other_root, 'dest/__pycache__'))
        self.assertFalse(self.exists(self.other_root, 'dest/.DS_Store'))
        self.assertEqual(len(result['touched']), 2)
        self.assertEqual(
            sorted(item['root'] for item in result['touched']),
            ['other', 'other'],
        )

    def test_revert_removes_every_copied_file(self):
        self.make_source_tree()
        run = self.run_bundle('COPY src', 'TO: other:dest')
        reverted = self.revert(run)

        self.assertEqual(self.last(reverted)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.other_root, 'dest/a.py'))
        self.assertFalse(self.exists(self.other_root, 'dest/sub/b.md'))
        self.assertTrue(self.exists(self.project_root, 'src/a.py'))

    def test_a_differing_file_refuses_the_whole_copy(self):
        self.make_source_tree()
        self.put(self.project_root, 'dest/a.py', 'different\n')
        run = self.run_bundle('COPY src', 'TO: dest')

        self.assertEqual(self.last(run)['status'], 'FAILED_EXISTS')
        self.assertIn('a.py', self.last(run)['message'])
        self.assertFalse(self.exists(self.project_root, 'dest/sub/b.md'))
        self.assertEqual(self.text(self.project_root, 'dest/a.py'), 'different\n')

    def test_identical_files_are_unchanged_not_conflicts(self):
        self.make_source_tree()
        self.put(self.project_root, 'dest/a.py', 'print("a")\n')
        run = self.run_bundle('COPY src', 'TO: dest')

        result = self.last(run)
        self.assertEqual(result['status'], 'APPLIED', result.get('message'))
        self.assertEqual(result['data']['unchanged'], 1)
        self.assertEqual(result['data']['created'], 1)
        self.assertEqual(len(result['touched']), 1)

    def test_overwrite_yes_replaces_and_keeps_extras(self):
        self.make_source_tree()
        self.put(self.project_root, 'dest/a.py', 'old\n')
        self.put(self.project_root, 'dest/extra.txt', 'keep me\n')
        run = self.run_bundle('COPY src', 'TO: dest', 'OVERWRITE: yes')

        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertEqual(self.text(self.project_root, 'dest/a.py'), 'print("a")\n')
        self.assertTrue(self.exists(self.project_root, 'dest/extra.txt'))

    def test_overwrite_replace_removes_extras_and_revert_restores_them(self):
        self.make_source_tree()
        self.put(self.project_root, 'dest/extra.txt', 'restore me\n')
        self.put(self.project_root, 'dest/__pycache__/x.pyc', b'\xff')
        run = self.run_bundle('COPY src', 'TO: dest', 'OVERWRITE: replace')

        result = self.last(run)
        self.assertEqual(result['status'], 'APPLIED', result.get('message'))
        self.assertEqual(result['data']['removed'], 1)
        self.assertFalse(self.exists(self.project_root, 'dest/extra.txt'))
        # Excluded names are never removed, even by replace.
        self.assertTrue(self.exists(self.project_root, 'dest/__pycache__/x.pyc'))

        self.revert(run)
        self.assertEqual(
            self.text(self.project_root, 'dest/extra.txt'), 'restore me\n',
        )
        self.assertFalse(self.exists(self.project_root, 'dest/a.py'))

    def test_a_binary_file_refuses_the_copy_and_is_named(self):
        self.make_source_tree()
        self.put(self.project_root, 'src/sprite.png', b'\x89PNG\xff\x00')
        run = self.run_bundle('COPY src', 'TO: dest')

        result = self.last(run)
        self.assertEqual(result['status'], 'FAILED_NOT_TEXT')
        self.assertIn('sprite.png', result['message'])
        self.assertFalse(self.exists(self.project_root, 'dest'))

    def test_exclude_and_glob_filter_the_tree(self):
        self.make_source_tree()
        self.put(self.project_root, 'src/sprite.png', b'\x89PNG\xff\x00')
        run = self.run_bundle(
            'COPY src', 'TO: dest', 'GLOB: *.py', 'EXCLUDE: *.png',
        )

        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertTrue(self.exists(self.project_root, 'dest/a.py'))
        self.assertFalse(self.exists(self.project_root, 'dest/sub/b.md'))

    def test_dry_run_writes_nothing(self):
        self.make_source_tree()
        run = self.run_bundle('COPY src', 'TO: dest', 'DRY_RUN: yes')

        result = self.last(run)
        self.assertEqual(result['status'], 'APPLIED')
        self.assertTrue(result['message'].startswith('Dry run'))
        self.assertIn('+ a.py', result['preview'])
        self.assertFalse(self.exists(self.project_root, 'dest'))
        self.assertFalse(result.get('touched'))

    def test_large_copies_need_confirm(self):
        for index in range(201):
            self.put(self.project_root, 'many/f%03d.txt' % index, str(index))

        refused = self.run_bundle('COPY many', 'TO: copied')
        self.assertEqual(self.last(refused)['status'], 'FAILED_NEEDS_CONFIRM')
        self.assertFalse(self.exists(self.project_root, 'copied'))

        allowed = self.run_bundle('COPY many', 'TO: copied', 'CONFIRM: yes')
        self.assertEqual(self.last(allowed)['status'], 'APPLIED')
        self.assertTrue(self.exists(self.project_root, 'copied/f200.txt'))

    def test_overlapping_paths_are_refused(self):
        self.make_source_tree()
        run = self.run_bundle('COPY src', 'TO: src/inner')

        self.assertEqual(self.last(run)['status'], 'FAILED_INVALID_PATH')
        self.assertFalse(self.exists(self.project_root, 'src/inner'))

    def test_a_single_file_cannot_target_an_existing_directory(self):
        self.put(self.project_root, 'one.txt', 'one\n')
        os.makedirs(os.path.join(self.project_root, 'folder'))
        run = self.run_bundle('COPY one.txt', 'TO: folder')

        self.assertEqual(self.last(run)['status'], 'FAILED_EXISTS')


class MoveDirectories(TransferCase):

    def test_moves_a_tree_across_roots_and_revert_puts_it_back(self):
        self.put(self.project_root, 'game/model.py', 'x = 1\n')
        self.put(self.project_root, 'game/smokes/check.py', 'y = 2\n')
        run = self.run_bundle('MOVE game', 'TO: other:games/game')

        result = self.last(run)
        self.assertEqual(result['status'], 'APPLIED', result.get('message'))
        self.assertEqual(self.text(self.other_root, 'games/game/model.py'), 'x = 1\n')
        self.assertFalse(self.exists(self.project_root, 'game'))
        self.assertEqual(len(result['touched']), 4)

        reverted = self.revert(run)
        self.assertEqual(self.last(reverted)['status'], 'APPLIED')
        self.assertEqual(self.text(self.project_root, 'game/smokes/check.py'), 'y = 2\n')
        self.assertFalse(self.exists(self.other_root, 'games/game/model.py'))

    def test_filtered_files_stay_behind_with_their_directory(self):
        self.put(self.project_root, 'game/model.py', 'x = 1\n')
        self.put(self.project_root, 'game/__pycache__/model.pyc', b'\x00\xff')
        run = self.run_bundle('MOVE game', 'TO: moved')

        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.project_root, 'game/model.py'))
        self.assertTrue(self.exists(self.project_root, 'game/__pycache__/model.pyc'))
        self.assertTrue(self.exists(self.project_root, 'moved/model.py'))

    def test_moves_a_single_file(self):
        self.put(self.project_root, 'old_name.py', 'z = 3\n')
        run = self.run_bundle('MOVE old_name.py', 'TO: new_name.py')

        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.project_root, 'old_name.py'))
        self.assertEqual(self.text(self.project_root, 'new_name.py'), 'z = 3\n')

    def test_a_refused_move_leaves_the_source_untouched(self):
        self.put(self.project_root, 'game/model.py', 'x = 1\n')
        self.put(self.project_root, 'game/art.png', b'\x89PNG\xff')
        run = self.run_bundle('MOVE game', 'TO: moved')

        self.assertEqual(self.last(run)['status'], 'FAILED_NOT_TEXT')
        self.assertTrue(self.exists(self.project_root, 'game/model.py'))
        self.assertFalse(self.exists(self.project_root, 'moved'))


class DeleteIsExact(TransferCase):

    def test_delete_refuses_a_binary_file_rather_than_record_garbage(self):
        self.put(self.project_root, 'art.png', b'\x89PNG\xff\x00')
        run = self.run_bundle('DELETE art.png')

        self.assertEqual(self.last(run)['status'], 'FAILED_NOT_TEXT')
        self.assertTrue(self.exists(self.project_root, 'art.png'))

    def test_delete_then_revert_restores_crlf_exactly(self):
        self.put(self.project_root, 'notes.txt', 'one\r\ntwo\r\n')
        run = self.run_bundle('DELETE notes.txt')
        self.assertEqual(self.last(run)['status'], 'APPLIED')

        self.revert(run)
        self.assertEqual(self.text(self.project_root, 'notes.txt'), 'one\r\ntwo\r\n')


if __name__ == '__main__':
    unittest.main()