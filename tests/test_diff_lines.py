# -*- coding: utf-8 -*-
"""
DIFF shows real changes, not positional line mismatches.

Before this, one inserted line made every later line of the file show as
changed. These tests pin the difflib-based output.
"""

import unittest

from forge_case import ForgeCase, bundle


def diff_op():
    from forge.packages.core_ops.diff import op
    return op


BEFORE = 'a\nb\nc\nd\ne\nf\ng\n'


class DiffLines(unittest.TestCase):

    def test_insert_is_one_added_line(self):
        after = 'a\nNEW\nb\nc\nd\ne\nf\ng\n'
        lines = diff_op()._diff_lines(BEFORE, after)
        self.assertIn('  + 0002  NEW', lines)
        self.assertFalse([line for line in lines if line.startswith('  - ')])
        # header, up to two context lines each side, the added line
        self.assertLessEqual(len(lines), 6)
        self.assertEqual(diff_op()._changed_ranges(BEFORE, after), '2 (+1)')

    def test_replacement_shows_old_and_new(self):
        lines = diff_op()._diff_lines('a\nb\nc\n', 'a\nB\nc\n')
        self.assertIn('  - 0002  b', lines)
        self.assertIn('  + 0002  B', lines)
        self.assertEqual(
            diff_op()._changed_ranges('a\nb\nc\n', 'a\nB\nc\n'), '2 (+1 -1)')

    def test_deletion(self):
        self.assertEqual(
            diff_op()._changed_ranges('a\nb\nc\n', 'a\nc\n'), 'after 1 (-1)')
        self.assertIn('  - 0002  b', diff_op()._diff_lines('a\nb\nc\n', 'a\nc\n'))

    def test_no_change(self):
        self.assertEqual(diff_op()._diff_lines(BEFORE, BEFORE), [])
        self.assertEqual(diff_op()._changed_ranges(BEFORE, BEFORE), 'none')

    def test_output_is_capped(self):
        before = ''.join('old %d\n' % n for n in range(500))
        after = ''.join('new %d\n' % n for n in range(500))
        lines = diff_op()._diff_lines(before, after)
        self.assertEqual(len(lines), diff_op().MAX_DIFF_LINES + 1)
        self.assertIn('more diff lines', lines[-1])


class DiffAfterInsert(ForgeCase):

    def test_diff_current_shows_only_the_insert(self):
        self.put('notes.txt', BEFORE)
        run = self.run_bundle(bundle(
            'INSERT notes.txt',
            'ANCHOR: a',
            'POSITION: after',
            'BEGIN_BODY',
            'NEW',
            'END_BODY',
            '',
            'DIFF current',
            'MODE: full',
        ))
        self.assertEqual(run.get('status'), 'APPLIED')
        preview = run['results'][1]['preview']
        self.assertIn('+ 0002  NEW', preview)
        self.assertNotIn('- 0003', preview)
        self.assertNotIn('0007', preview)


if __name__ == '__main__':
    unittest.main()