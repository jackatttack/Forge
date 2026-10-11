# -*- coding: utf-8 -*-
"""
Text edits preserve every byte they do not deliberately change, and record
the exact original so REVERT restores it byte for byte.

Tests marked expectedFailure pin damage that Forge does today: text-mode
reads turn CRLF into LF and undecodable bytes into U+FFFD, and the writes
put that normalised text back. When the exact-file-state work fixes one,
unittest reports an unexpected success and the suite fails, which is the
signal to remove that decorator.
"""

import hashlib
import os
import unittest

from forge_case import ForgeCase, bundle
from forge.core.content_records import collect_changes


CRLF_FILE = b'alpha\r\nbeta\r\ngamma\r\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


class TextEditCase(ForgeCase):

    def put_bytes(self, name, data):
        with open(os.path.join(self.project_root, name), 'wb') as handle:
            handle.write(data)

    def get_bytes(self, name):
        with open(os.path.join(self.project_root, name), 'rb') as handle:
            return handle.read()

    def replace(self, name, old, new):
        return self.run_bundle(bundle(
            'REPLACE ' + name,
            'BEGIN_OLD', old, 'END_OLD',
            'BEGIN_NEW', new, 'END_NEW',
        ))


class LineEndingsSurviveEdits(TextEditCase):

    def setUp(self):
        super().setUp()
        self.put_bytes('notes.txt', CRLF_FILE)

    def test_replace_keeps_crlf(self):
        run = self.replace('notes.txt', 'beta', 'BETA')
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get_bytes('notes.txt'), b'alpha\r\nBETA\r\ngamma\r\n')

    def test_multiline_lf_old_matches_crlf_and_keeps_it(self):
        run = self.replace('notes.txt', 'alpha\nbeta', 'ALPHA\nBETA')
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get_bytes('notes.txt'), b'ALPHA\r\nBETA\r\ngamma\r\n')

    def test_insert_writes_new_lines_in_crlf(self):
        run = self.run_bundle(bundle(
            'INSERT notes.txt',
            'ANCHOR: alpha',
            'POSITION: after',
            'BEGIN_BODY', 'inserted', 'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(
            self.get_bytes('notes.txt'), b'alpha\r\ninserted\r\nbeta\r\ngamma\r\n')

    def test_delete_lines_keeps_crlf(self):
        run = self.run_bundle(bundle('DELETE notes.txt', 'LINES: 2-2'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get_bytes('notes.txt'), b'alpha\r\ngamma\r\n')

    def test_recorded_original_is_the_exact_crlf_bytes(self):
        run = self.replace('notes.txt', 'beta', 'BETA')
        changes = collect_changes(run)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['before_sha'], sha(CRLF_FILE))

    def test_replace_lines_keeps_crlf(self):
        run = self.run_bundle(bundle(
            'REPLACE notes.txt', 'LINES: 2-2', 'BEGIN_BODY', 'BETA', 'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get_bytes('notes.txt'), b'alpha\r\nBETA\r\ngamma\r\n')

    def assert_all_crlf(self, data):
        self.assertEqual(data.count(b'\r\n'), data.count(b'\n'))

    def test_replace_python_target_keeps_crlf(self):
        self.put_bytes('code.py', b'def a():\r\n    return 1\r\n')
        run = self.run_bundle(bundle(
            'REPLACE code.py::a',
            'BEGIN_BODY', 'def a():', '    return 3', 'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        data = self.get_bytes('code.py')
        self.assertIn(b'return 3', data)
        self.assert_all_crlf(data)

    def test_insert_python_target_keeps_crlf(self):
        self.put_bytes('code.py', b'def a():\r\n    return 1\r\n')
        run = self.run_bundle(bundle(
            'INSERT code.py::a', 'POSITION: after',
            'BEGIN_BODY', 'def b():', '    return 2', 'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        data = self.get_bytes('code.py')
        self.assertIn(b'def b():', data)
        self.assert_all_crlf(data)


class UndecodableBytesAreNeverRewritten(TextEditCase):

    def test_text_edit_refuses_invalid_utf8_and_leaves_bytes(self):
        original = b'ok\nbad \xff byte\n'
        self.put_bytes('mixed.txt', original)
        run = self.replace('mixed.txt', 'ok', 'OK')
        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.get_bytes('mixed.txt'), original)

    def test_write_over_binary_records_the_exact_original(self):
        original = b'\x89PNG\r\n\x1a\n\x00\xff\xfe'
        self.put_bytes('image.png', original)
        run = self.run_bundle(bundle(
            'WRITE image.png',
            'CONFIRM: overwrite',
            'BEGIN_BODY', 'replacement', 'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertTrue(self.get_bytes('image.png').startswith(b'replacement'))
        self.assertEqual(collect_changes(run)[0]['before_sha'], sha(original))


class AlreadyCorrect(TextEditCase):
    """Behaviour that works today and must keep working."""

    def test_lf_file_stays_lf(self):
        self.put_bytes('notes.txt', b'alpha\nbeta\n')
        self.replace('notes.txt', 'beta', 'BETA')
        self.assertEqual(self.get_bytes('notes.txt'), b'alpha\nBETA\n')

    def test_bom_is_kept(self):
        self.put_bytes('notes.txt', b'\xef\xbb\xbfalpha\nbeta\n')
        self.replace('notes.txt', 'beta', 'BETA')
        self.assertEqual(self.get_bytes('notes.txt'), b'\xef\xbb\xbfalpha\nBETA\n')

    def test_non_ascii_is_kept(self):
        self.put_bytes('notes.txt', 'café\nbeta\n'.encode('utf-8'))
        self.replace('notes.txt', 'beta', 'BETA')
        self.assertEqual(self.get_bytes('notes.txt'), 'café\nBETA\n'.encode('utf-8'))


if __name__ == '__main__':
    unittest.main(verbosity=2)