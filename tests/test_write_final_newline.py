# -*- coding: utf-8 -*-
"""
WRITE FINAL_NEWLINE: bundle bodies drop trailing blank lines, so this
directive is the only way to write a file that ends with a newline.
"""

import unittest

from forge_case import ForgeCase, bundle


def write_bundle(path, *directives):
    return bundle(
        'WRITE ' + path,
        *directives,
        'BEGIN_BODY',
        'hello',
        '',
        '',
        'END_BODY',
    )


class FinalNewline(ForgeCase):

    def test_yes_adds_exactly_one_newline(self):
        run = self.run_bundle(write_bundle('out.txt', 'FINAL_NEWLINE: yes'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get('out.txt'), 'hello\n')

    def test_without_the_directive_no_newline_is_written(self):
        run = self.run_bundle(write_bundle('out.txt'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get('out.txt'), 'hello')

    def test_no_writes_no_newline(self):
        run = self.run_bundle(write_bundle('out.txt', 'FINAL_NEWLINE: no'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get('out.txt'), 'hello')

    def test_invalid_value_fails_before_anything_runs(self):
        run = self.run_bundle(write_bundle('out.txt', 'FINAL_NEWLINE: maybe'))
        self.assertEqual(run.get('status'), 'FAILED_PARSE')
        self.assertFalse(self.exists('out.txt'))

    def test_identical_file_with_newline_is_unchanged(self):
        self.put('notes.txt', 'hello\n')
        run = self.run_bundle(write_bundle('notes.txt', 'FINAL_NEWLINE: yes'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(self.get('notes.txt'), 'hello\n')


if __name__ == '__main__':
    unittest.main()