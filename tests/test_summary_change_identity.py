# -*- coding: utf-8 -*-
"""
The standard summary counts changed files by root and path, using the
same collector as the packet, run storage and DIFF.
"""

import unittest

from forge.core.presentation.standard import format_summary


def change(relative, root=''):
    """A plain text change record, shaped like those operations record."""
    return {
        'rel': relative, 'root': root, 'kind': 'file',
        'before': 'old', 'after': 'new',
        'existed_before': True, 'existed_after': True,
    }


class SummaryChangeIdentity(unittest.TestCase):

    def test_same_name_in_two_roots_counts_twice(self):
        summary = format_summary({
            'status': 'applied',
            'touched_files': [change('a.txt'), change('a.txt', root='icloud')],
        })
        self.assertIn('Changed: 2 files', summary)

    def test_one_file_reported_twice_counts_once(self):
        record = change('a.txt')
        summary = format_summary({
            'status': 'applied',
            'touched_files': [record],
            'results': [{'touched': [record]}],
        })
        self.assertIn('Changed: 1 file\n', summary)

    def test_equivalent_spellings_of_one_path_count_once(self):
        summary = format_summary({
            'status': 'applied',
            'touched_files': [change('dir/a.txt'), change('./dir/a.txt')],
        })
        self.assertIn('Changed: 1 file\n', summary)


if __name__ == '__main__':
    unittest.main()