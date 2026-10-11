# -*- coding: utf-8 -*-
"""Exact snapshots and failure-safe writes for binary transfer support."""

import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch

from forge_case import forge
from forge.core import file_content


class FileContentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='forge-content-test-')
        self.addCleanup(self.directory.cleanup)
        self.store = file_content.ContentStore()
        self.addCleanup(self.store.close)

    def path(self, name):
        return os.path.join(self.directory.name, name)

    def put(self, name, data):
        path = self.path(name)
        with open(path, 'wb') as handle:
            handle.write(data)
        return path

    def get(self, name):
        with open(self.path(name), 'rb') as handle:
            return handle.read()

    def test_text_preserves_crlf_bom_and_empty_contents(self):
        for index, data in enumerate((
            b'', b'one\r\ntwo\r\n', b'\xef\xbb\xbfhello\n',
        )):
            content = self.store.capture(self.put(str(index), data))
            self.assertEqual(content['encoding'], 'utf-8')
            file_content.atomic_install(self.path('copy'), content)
            self.assertEqual(self.get('copy'), data)

    def test_binary_snapshot_survives_source_changes(self):
        original = bytes(range(256)) * 100
        source = self.put('source', original)
        content = self.store.capture(source)
        self.put('source', b'changed')
        self.assertEqual(content['encoding'], 'blob')
        file_content.atomic_install(self.path('copy'), content)
        self.assertEqual(self.get('copy'), original)
        self.assertFalse(file_content.matches_file(source, content))

    def test_large_valid_utf8_is_file_backed(self):
        data = b'x' * (file_content.INLINE_TEXT_BYTES + 1)
        content = self.store.capture(self.put('large', data))
        self.assertEqual(content['encoding'], 'blob')
        self.assertNotIn('text', content)
        self.assertEqual(content['size'], len(data))
        self.assertEqual(content['sha256'], hashlib.sha256(data).hexdigest())
        self.assertLessEqual(
            max(map(len, file_content.content_chunks(content))),
            file_content.CHUNK_BYTES,
        )

    def test_nul_is_binary_even_when_valid_utf8(self):
        content = self.store.capture(self.put('nul', b'abc\x00def'))
        self.assertEqual(content['encoding'], 'blob')

    def test_corrupt_snapshot_preserves_destination_and_cleans_stage(self):
        content = self.store.capture(self.put('source', b'\x89PNG\xff'))
        with open(content['path'], 'wb') as handle:
            handle.write(b'corrupt')
        self.put('destination', b'keep')
        with self.assertRaises(ValueError):
            file_content.atomic_install(self.path('destination'), content)
        self.assertEqual(self.get('destination'), b'keep')
        self.assertFalse(any(
            name.startswith('.forge-content-')
            for name in os.listdir(self.directory.name)
        ))

    def test_replace_failure_preserves_destination(self):
        content = file_content.text_content('new')
        self.put('destination', b'old')
        with patch.object(
            file_content.os, 'replace', side_effect=OSError('injected'),
        ):
            with self.assertRaises(OSError):
                file_content.atomic_install(self.path('destination'), content)
        self.assertEqual(self.get('destination'), b'old')

    def test_recheck_failure_preserves_newer_destination(self):
        content = file_content.text_content('planned')
        self.put('destination', b'old')

        def refuse():
            self.put('destination', b'newer work')
            raise OSError('Destination changed')

        with self.assertRaises(OSError):
            file_content.atomic_install(
                self.path('destination'), content, before_replace=refuse,
            )
        self.assertEqual(self.get('destination'), b'newer work')

    def test_snapshot_cleanup_is_explicit_and_repeatable(self):
        content = self.store.capture(self.put('binary', b'\xff'))
        snapshot = content['path']
        self.assertTrue(os.path.exists(snapshot))
        self.store.close()
        self.store.close()
        self.assertFalse(os.path.exists(snapshot))

    def test_identity_does_not_depend_on_storage_encoding(self):
        text = file_content.text_content('hello')
        path = self.put('raw', b'hello')
        blob = {
            'encoding': 'blob',
            'path': path,
            'size': text['size'],
            'sha256': text['sha256'],
        }
        self.assertTrue(file_content.same_content(text, blob))
        file_content.verify_content(blob)


if __name__ == '__main__':
    unittest.main()