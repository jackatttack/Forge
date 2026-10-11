# -*- coding: utf-8 -*-
"""Binary transfers exercise the real runner, storage and recovery path."""

import os
from unittest.mock import patch

from test_copy_move import TransferCase
from forge.core import file_content, file_transfer


class BinaryTransferTests(TransferCase):
    def raw(self, root, relative):
        with open(os.path.join(root, relative), 'rb') as handle:
            return handle.read()

    def test_mixed_cross_root_move_and_undo_twice(self):
        self.put(self.project_root, 'src/code.py', 'x = 1\r\n')
        data = bytes(range(256)) * 5000
        self.put(self.project_root, 'src/sub/art.png', data)
        run = self.run_bundle('MOVE src', 'TO: other:dest')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.other_root, 'dest/sub/art.png'), data)
        self.assertFalse(self.exists(self.project_root, 'src'))
        self.assertNotIn('_content_store', run)
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.project_root, 'src/sub/art.png'), data)
        self.assertEqual(self.raw(self.project_root, 'src/code.py'), b'x = 1\r\n')
        redo = self.revert(recovery)
        self.assertEqual(self.last(redo)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.other_root, 'dest/sub/art.png'), data)

    def test_replace_restores_binary_extras_and_overwrites(self):
        self.put(self.project_root, 'src/art', b'\xffnew')
        self.put(self.project_root, 'dest/art', b'\xffold')
        self.put(self.project_root, 'dest/extra', b'\xffextra')
        run = self.run_bundle('COPY src', 'TO: dest', 'OVERWRITE: replace')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.project_root, 'dest/extra'))
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.project_root, 'dest/art'), b'\xffold')
        self.assertEqual(self.raw(self.project_root, 'dest/extra'), b'\xffextra')

    def test_identical_binary_destination_is_unchanged(self):
        self.put(self.project_root, 'src', b'\xffsame')
        self.put(self.project_root, 'dest', b'\xffsame')
        run = self.run_bundle('COPY src', 'TO: dest')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertEqual(self.last(run)['data']['unchanged'], 1)
        self.assertFalse(run.get('touched_files'))

    def test_binary_dry_run_does_not_change_workspace(self):
        self.put(self.project_root, 'src', b'\xffsource')
        run = self.run_bundle('MOVE src', 'TO: dest', 'DRY_RUN: yes')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.project_root, 'src'), b'\xffsource')
        self.assertFalse(self.exists(self.project_root, 'dest'))
        self.assertFalse(run.get('touched_files'))
        self.assertNotIn('_content_store', run)

    def test_source_changed_after_copy_is_not_deleted(self):
        self.put(self.project_root, 'src', b'\xfforiginal')
        real_install = file_content.atomic_install

        def install_then_edit(path, content, before_replace=None):
            result = real_install(path, content, before_replace=before_replace)
            if path == os.path.join(self.project_root, 'dest'):
                self.put(self.project_root, 'src', b'\xffnewer')
            return result

        with patch.object(file_content, 'atomic_install', install_then_edit):
            run = self.run_bundle('MOVE src', 'TO: dest')
        self.assertEqual(self.last(run)['status'], 'FAILED_IO')
        self.assertEqual(self.raw(self.project_root, 'src'), b'\xffnewer')
        self.assertEqual(self.raw(self.project_root, 'dest'), b'\xfforiginal')
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertEqual(self.raw(self.project_root, 'src'), b'\xffnewer')
        self.assertFalse(self.exists(self.project_root, 'dest'))

    def test_failed_second_write_is_recorded_and_recoverable(self):
        self.put(self.project_root, 'src/a', b'\xffa')
        self.put(self.project_root, 'src/b', b'\xffb')
        self.put(self.project_root, 'dest/b', b'\xffkeep')
        real_replace = os.replace

        def fail_second(source, destination):
            if destination == os.path.join(self.project_root, 'dest/b'):
                raise OSError('Injected transfer failure')
            return real_replace(source, destination)

        with patch.object(file_content.os, 'replace', fail_second):
            run = self.run_bundle('COPY src', 'TO: dest', 'OVERWRITE: yes')
        self.assertEqual(self.last(run)['status'], 'FAILED_IO')
        self.assertEqual(self.raw(self.project_root, 'dest/b'), b'\xffkeep')
        self.assertEqual([item['rel'] for item in run['touched_files']], ['dest/a'])
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.project_root, 'dest/a'))
        self.assertEqual(self.raw(self.project_root, 'dest/b'), b'\xffkeep')