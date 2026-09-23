# -*- coding: utf-8 -*-
"""
The stale-read guard: IF_VERSION pins a mutation to the file version the
model last saw, and a stale pin leaves the file untouched.
"""

import hashlib
import unittest

from forge_case import ForgeCase, bundle


def version_of(text):
    """The version Forge reports for a file containing exactly text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:8]


class PinnedWrite(ForgeCase):

    def test_current_pin_applies(self):
        self.put('notes.txt', 'original\n')
        run = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: ' + version_of('original\n'),
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertTrue(self.get('notes.txt').startswith('replacement'))

    def test_prefixed_pin_is_accepted(self):
        self.put('notes.txt', 'original\n')
        run = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: v:' + version_of('original\n'),
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])

    def test_stale_pin_leaves_file_untouched_and_stops_later_edits(self):
        self.put('notes.txt', 'original\n')
        run = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: 00000000',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
            '',
            'WRITE second.txt',
            'BEGIN_BODY',
            'should not be created',
            'END_BODY',
        ))
        self.assertEqual(
            self.statuses(run),
            ['SKIPPED_STALE_READ', 'SKIPPED_AFTER_FAILURE'],
        )
        self.assertEqual(self.get('notes.txt'), 'original\n')
        self.assertFalse(self.exists('second.txt'))

    def test_pins_are_checked_against_bundle_start(self):
        """Two edits in one bundle may both pin the version that was read."""
        self.put('notes.txt', 'original\n')
        pin = 'IF_VERSION: ' + version_of('original\n')
        run = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            pin,
            'BEGIN_BODY',
            'first',
            'END_BODY',
            '',
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            pin,
            'BEGIN_BODY',
            'second',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED', 'APPLIED'])
        self.assertTrue(self.get('notes.txt').startswith('second'))


class PinnedCreation(ForgeCase):

    def test_missing_pin_creates_a_new_file(self):
        run = self.run_bundle(bundle(
            'WRITE fresh.txt',
            'IF_VERSION: missing',
            'BEGIN_BODY',
            'hello',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertTrue(self.exists('fresh.txt'))

    def test_missing_pin_refuses_an_existing_file(self):
        self.put('notes.txt', 'original\n')
        run = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: missing',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['SKIPPED_STALE_READ'])
        self.assertEqual(self.get('notes.txt'), 'original\n')


class PinnedEdits(ForgeCase):
    """REPLACE, INSERT and DELETE honour IF_VERSION exactly as WRITE does."""

    ORIGINAL = 'value = 1\n'
    STALE = 'IF_VERSION: 00000000'

    def setUp(self):
        super().setUp()
        self.put('notes.txt', self.ORIGINAL)

    def current(self):
        return 'IF_VERSION: ' + version_of(self.ORIGINAL)

    def replace_with(self, pin):
        return self.run_bundle(bundle(
            'REPLACE notes.txt',
            pin,
            'BEGIN_OLD',
            'value = 1',
            'END_OLD',
            'BEGIN_NEW',
            'value = 2',
            'END_NEW',
        ))

    def insert_with(self, pin):
        return self.run_bundle(bundle(
            'INSERT notes.txt',
            'LINE: 1',
            'POSITION: after',
            pin,
            'BEGIN_BODY',
            'value = 2',
            'END_BODY',
        ))

    def delete_with(self, pin):
        return self.run_bundle(bundle('DELETE notes.txt', pin))

    def test_replace_with_current_pin_applies(self):
        self.assertEqual(self.statuses(self.replace_with(self.current())), ['APPLIED'])
        self.assertIn('value = 2', self.get('notes.txt'))

    def test_replace_with_stale_pin_is_refused(self):
        self.assertEqual(self.statuses(self.replace_with(self.STALE)), ['SKIPPED_STALE_READ'])
        self.assertEqual(self.get('notes.txt'), self.ORIGINAL)

    def test_insert_with_current_pin_applies(self):
        self.assertEqual(self.statuses(self.insert_with(self.current())), ['APPLIED'])
        self.assertIn('value = 2', self.get('notes.txt'))

    def test_insert_with_stale_pin_is_refused(self):
        self.assertEqual(self.statuses(self.insert_with(self.STALE)), ['SKIPPED_STALE_READ'])
        self.assertEqual(self.get('notes.txt'), self.ORIGINAL)

    def test_delete_with_current_pin_applies(self):
        self.assertEqual(self.statuses(self.delete_with(self.current())), ['APPLIED'])
        self.assertFalse(self.exists('notes.txt'))

    def test_delete_with_stale_pin_is_refused(self):
        self.assertEqual(self.statuses(self.delete_with(self.STALE)), ['SKIPPED_STALE_READ'])
        self.assertEqual(self.get('notes.txt'), self.ORIGINAL)


class VersionReporting(ForgeCase):
    """Versions reach the packet, so a model never needs an extra READ."""

    def test_read_header_shows_the_file_version(self):
        self.put('notes.txt', 'original\n')
        result = self.run_bundle(bundle('READ notes.txt'))['results'][0]
        header = result['preview'].splitlines()[0]
        self.assertIn('v:' + version_of('original\n'), header)

    def test_ast_read_header_shows_the_whole_file_version(self):
        source = 'def main():\n    return 1\n'
        self.put('app.py', source)
        result = self.run_bundle(bundle('READ app.py::main'))['results'][0]
        self.assertEqual(result['status'], 'APPLIED', result.get('message'))
        header = result['preview'].splitlines()[0]
        self.assertIn('v:' + version_of(source), header)

    def test_edit_reports_the_version_it_left_behind(self):
        self.put('notes.txt', 'original\n')
        result = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))['results'][0]
        expected = version_of(self.get('notes.txt'))
        self.assertEqual(result['version_after'], expected)
        self.assertIn('v:' + expected, result['message'])

    def test_reported_version_pins_the_next_bundle(self):
        """The version from one packet is a valid pin in the next."""
        self.put('notes.txt', 'original\n')
        first = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'BEGIN_BODY',
            'first',
            'END_BODY',
        ))['results'][0]
        second = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: ' + first['version_after'],
            'BEGIN_BODY',
            'second',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(second), ['APPLIED'])
        self.assertTrue(self.get('notes.txt').startswith('second'))

    def test_stale_refusal_does_not_reveal_the_current_version(self):
        """The only route to a valid pin is to look at the file again."""
        self.put('notes.txt', 'original\n')
        result = self.run_bundle(bundle(
            'WRITE notes.txt',
            'CONFIRM: overwrite',
            'IF_VERSION: 00000000',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))['results'][0]
        self.assertNotIn(version_of('original\n'), result['message'])


if __name__ == '__main__':
    unittest.main()