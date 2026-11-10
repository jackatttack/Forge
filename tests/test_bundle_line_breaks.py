# -*- coding: utf-8 -*-
"""
Only newlines end a line of a bundle.

str.splitlines() also breaks at form feeds, U+2028 and other characters.
Inside a body or an OLD block those are content; splitting there turned
them into newlines without a word.
"""

import os
import unittest

from forge_case import ForgeCase, bundle


class OnlyNewlinesBreakLines(ForgeCase):

    def exact(self, relative_path):
        path = os.path.join(self.project_root, relative_path)
        with open(path, 'r', encoding='utf-8', newline='') as handle:
            return handle.read()

    def test_form_feed_and_line_separator_survive_in_a_body(self):
        run = self.run_bundle(
            bundle(
                'ENV: pythonista',
                'WRITE page.txt',
                'BEGIN_BODY',
                'one\x0ctwo',
                'three\u2028four',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run.get('packet'))
        self.assertEqual(self.exact('page.txt'), 'one\x0ctwo\nthree\u2028four')

    def test_old_block_holding_a_form_feed_matches(self):
        path = os.path.join(self.project_root, 'notes.txt')
        with open(path, 'w', encoding='utf-8', newline='') as handle:
            handle.write('a\x0cb\nend\n')

        run = self.run_bundle(
            bundle(
                'REPLACE notes.txt',
                'BEGIN_OLD',
                'a\x0cb',
                'END_OLD',
                'BEGIN_NEW',
                'ab',
                'END_NEW',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run.get('packet'))
        self.assertEqual(self.exact('notes.txt'), 'ab\nend\n')

    def test_crlf_bundle_still_parses(self):
        run = self.run_bundle(
            'WRITE a.txt\r\nBEGIN_BODY\r\nhi\r\nEND_BODY\r\n'
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run.get('packet'))
        self.assertEqual(self.exact('a.txt'), 'hi')


if __name__ == '__main__':
    unittest.main()