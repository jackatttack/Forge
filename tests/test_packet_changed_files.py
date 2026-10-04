# -*- coding: utf-8 -*-
"""
The packet's Changed files line must describe what a run left behind.

Several changes to one file in a run are merged into one line, so the
line has to use the first change's "existed before" and the last
change's "existed after". Using only the first once reported a file
created and then deleted in the same run as "created · 0 lines".
"""

import unittest

from forge.core.protocol.packet import _format_changed_files


def touched(before, after, existed_before, existed_after=True):
    return {
        'rel': 'a.txt',
        'before': before,
        'after': after,
        'existed_before': existed_before,
        'existed_after': existed_after,
    }


class ChangedFilesSummary(unittest.TestCase):

    def summary(self, *items):
        lines = _format_changed_files({'results': [{'touched': list(items)}]})
        return [line for line in lines if line.startswith('- ')]

    def test_created_file_counts_its_lines(self):
        self.assertEqual(
            self.summary(touched('', 'x\n', False)),
            ['- a.txt — created · 1 lines'],
        )

    def test_deleted_file_says_deleted(self):
        self.assertEqual(
            self.summary(touched('x\ny\n', '', True, existed_after=False)),
            ['- a.txt — deleted · 2 lines'],
        )

    def test_created_then_deleted_in_one_run_says_so(self):
        self.assertEqual(
            self.summary(
                touched('', 'x\n', False),
                touched('x\n', '', True, existed_after=False),
            ),
            ['- a.txt — created and removed · no net change'],
        )


if __name__ == '__main__':
    unittest.main()