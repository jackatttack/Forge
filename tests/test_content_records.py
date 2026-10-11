# -*- coding: utf-8 -*-
"""Byte snapshots stay out of JSON and aggregation preserves true endpoints."""

import json
import os

from test_copy_move import TransferCase
from forge.core.file_content import ContentStore, text_content
from forge.core.content_records import (
    collect_changes, content_change, persist_run_contents,
)
from forge.core import run_storage


class ContentRecordTests(TransferCase):
    def setUp(self):
        super().setUp()
        self.content_store = ContentStore()
        self.addCleanup(self.content_store.close)

    def binary(self, name, data):
        self.put(self.project_root, name, data)
        return self.content_store.capture(os.path.join(self.project_root, name))

    def test_mixed_records_keep_first_and_final_state(self):
        binary = self.binary('source', b'\xff\x00')
        first = {
            'rel': 'a', 'root': '', 'kind': 'file',
            'before': 'original', 'after': 'middle',
            'existed_before': True, 'existed_after': True,
        }
        second = content_change('a', text_content('middle'), binary)
        final = content_change('a', binary, text_content('final'))
        changes = collect_changes({
            'touched_files': [first, second, final],
            'results': [{'touched': [first, second, final]}],
        })
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['before_content']['text'], 'original')
        self.assertEqual(changes[0]['after_content']['text'], 'final')

    def test_roots_remain_distinct_and_absence_is_not_empty(self):
        empty = text_content('')
        changes = collect_changes({'touched_files': [
            content_change('a', empty, empty, False, True),
            content_change('a', empty, empty, True, False, root='other'),
        ]})
        self.assertEqual(len(changes), 2)
        self.assertEqual(
            [(item['root'], item['existed_before'], item['existed_after'])
             for item in changes],
            [('', False, True), ('other', True, False)],
        )

    def test_binary_run_has_portable_verified_snapshots(self):
        before_bytes = b'\xff\x00original'
        after_bytes = b'\x89PNG\xff' * 100000
        before = self.binary('before', before_bytes)
        after = self.binary('after', after_bytes)

        run = self.run_bundle('FORGE ops')
        change = content_change('target.png', before, after)
        run['touched_files'] = [change]
        run['results'] = [{'touched': [change]}]
        directory = run_storage.write_run(run, environment=run['environment'])

        manifest, error = run_storage.read_manifest(
            self.project_root, run['stamp'], mode='test',
            environment=run['environment'],
        )
        self.assertIsNone(error)
        entry = manifest['touched'][0]
        for side, expected in (('before', before_bytes), ('after', after_bytes)):
            content = entry[side + '_content']
            self.assertNotIn('path', content)
            self.assertNotIn('text', content)
            with open(os.path.join(directory, content['snapshot_rel']), 'rb') as handle:
                self.assertEqual(handle.read(), expected)

        self.content_store.close()
        with open(os.path.join(directory, 'run.json'), encoding='utf-8') as handle:
            serialized = handle.read()
        json.loads(serialized)
        self.assertLess(len(serialized), 20000)
        self.assertNotIn("b'\\x", serialized)
        self.assertTrue(os.path.isfile(after['path']))

    def test_identical_payloads_share_one_persistent_snapshot(self):
        first = self.binary('one', b'\xffsame')
        second = self.binary('two', b'\xffsame')
        run = {'touched_files': [
            content_change('target', first, second),
        ]}
        directory = os.path.join(self.forge_home, 'blob-test')
        persist_run_contents(run, directory)
        self.assertEqual(first['snapshot_rel'], second['snapshot_rel'])
        self.assertEqual(
            len(os.listdir(os.path.join(directory, 'snapshots', 'blobs'))), 1,
        )