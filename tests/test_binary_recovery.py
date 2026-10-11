# -*- coding: utf-8 -*-
"""Content-aware recovery preserves bytes, newer work, and undo history."""

import json
import os
from unittest.mock import patch

from test_copy_move import TransferCase
from forge.core import run_storage
from forge.core.file_content import ContentStore, text_content
from forge.core.content_records import content_change


class BinaryRecoveryTests(TransferCase):
    def setUp(self):
        super().setUp()
        self.content_store = ContentStore()
        self.addCleanup(self.content_store.close)

    def capture(self, relative):
        return self.content_store.capture(
            os.path.join(self.project_root, relative),
        )

    def raw(self, relative):
        with open(os.path.join(self.project_root, relative), 'rb') as handle:
            return handle.read()

    def recorded_edit(self, before, after):
        self.put(self.project_root, 'target', before)
        original = self.capture('target')
        self.put(self.project_root, 'target', after)
        final = self.capture('target')
        run = self.run_bundle('FORGE ops')
        run['touched_files'] = [content_change('target', original, final)]
        run['results'] = []
        run['artifact_dir'] = run_storage.write_run(
            run, environment=run['environment'],
        )
        return run

    def test_binary_revert_and_revert_of_revert(self):
        original = self.recorded_edit(b'\xffold', b'\x89PNG\x00new')
        recovery = self.revert(original)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertEqual(self.raw('target'), b'\xffold')
        redo = self.revert(recovery)
        self.assertEqual(self.last(redo)['status'], 'APPLIED')
        self.assertEqual(self.raw('target'), b'\x89PNG\x00new')

    def test_both_text_binary_transition_directions(self):
        for before, after in (
            (b'hello\r\n', b'\xffbinary'),
            (b'\xffbinary', b'hello\r\n'),
        ):
            original = self.recorded_edit(before, after)
            recovery = self.revert(original)
            self.assertEqual(self.last(recovery)['status'], 'APPLIED')
            self.assertEqual(self.raw('target'), before)

    def test_binary_drift_refuses_recovery(self):
        original = self.recorded_edit(b'\xffold', b'\xffnew')
        self.put(self.project_root, 'target', b'\xffindependent')
        recovery = self.revert(original)
        self.assertEqual(self.last(recovery)['status'], 'FAILED_RECOVERY')
        self.assertEqual(self.raw('target'), b'\xffindependent')
        self.assertFalse(recovery.get('touched_files'))

    def test_corrupt_binary_snapshot_refuses_recovery(self):
        original = self.recorded_edit(b'\xffold', b'\xffnew')
        manifest, error = run_storage.read_manifest(
            self.project_root, original['stamp'], mode='test',
            environment=original['environment'],
        )
        self.assertIsNone(error)
        snapshot = manifest['touched'][0]['before_content']['snapshot_rel']
        with open(os.path.join(original['artifact_dir'], snapshot), 'wb') as handle:
            handle.write(b'corrupt')
        recovery = self.revert(original)
        self.assertEqual(self.last(recovery)['status'], 'FAILED_RECOVERY')
        self.assertEqual(self.raw('target'), b'\xffnew')

    def test_binary_created_file_can_be_deleted_and_recreated(self):
        data = b'\xffcreated'
        self.put(self.project_root, 'target', data)
        run = self.run_bundle('FORGE ops')
        run['touched_files'] = [
            content_change(
                'target', text_content(''), self.capture('target'),
                existed_before=False, existed_after=True,
            ),
        ]
        run['results'] = []
        run_storage.write_run(run, environment=run['environment'])
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        self.assertFalse(self.exists(self.project_root, 'target'))
        redo = self.revert(recovery)
        self.assertEqual(self.last(redo)['status'], 'APPLIED')
        self.assertEqual(self.raw('target'), data)

    def test_binary_atomic_install_failure_preserves_target(self):
        original = self.recorded_edit(b'\xffold', b'\xffnew')
        from forge.core import file_content
        real_replace = file_content.os.replace

        def fail_target(source, destination):
            if destination == os.path.join(self.project_root, 'target'):
                raise OSError('Injected recovery failure')
            return real_replace(source, destination)

        with patch.object(file_content.os, 'replace', fail_target):
            recovery = self.revert(original)
        self.assertEqual(self.last(recovery)['status'], 'FAILED_RECOVERY')
        self.assertEqual(self.raw('target'), b'\xffnew')
        self.assertFalse(recovery.get('touched_files'))

    def test_snapshot_path_escape_is_refused(self):
        original = self.recorded_edit(b'\xffold', b'\xffnew')
        path = os.path.join(original['artifact_dir'], 'manifest.json')
        with open(path, encoding='utf-8') as handle:
            manifest = json.load(handle)
        manifest['touched'][0]['before_content']['snapshot_rel'] = '../outside'
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle)
        recovery = self.revert(original)
        self.assertEqual(self.last(recovery)['status'], 'FAILED_RECOVERY')
        self.assertEqual(self.raw('target'), b'\xffnew')