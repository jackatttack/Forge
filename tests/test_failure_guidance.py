# -*- coding: utf-8 -*-
"""
Failures that answer the next question.

An ambiguous anchor names the lines it matched, so OCCURRENCE can be
chosen without another READ. An OLD block that matches nothing names the
closest block and its first differing line, so drift shows at once.
"""

import unittest

from forge_case import ForgeCase, bundle

from forge.core.near_match import (
    closest_block,
    describe_closest,
    format_line_numbers,
)


SOURCE = 'def main():\n    value = 1\n    return value\n'


def first_message(run):
    results = run.get('results') or [{}]
    return str(results[0].get('message') or '')


class AmbiguousAnchorsNameTheirLines(ForgeCase):

    def test_plain_file_anchor_lists_matching_lines(self):
        self.put('notes.txt', 'a\nmark\nb\nmark\n')
        run = self.run_bundle(bundle(
            'INSERT notes.txt',
            'ANCHOR: mark',
            'POSITION: after',
            'BEGIN_BODY',
            'new',
            'END_BODY',
        ))
        message = first_message(run)
        self.assertIn('lines 2, 4', message)
        self.assertTrue(message.startswith('ANCHOR matched'), message)

    def test_ast_anchor_reports_file_lines(self):
        self.put(
            'app.py',
            'x = 1\n\n\ndef main():\n    mark = 1\n    mark = 2\n',
        )
        run = self.run_bundle(bundle(
            'INSERT app.py::main',
            'ANCHOR: mark',
            'POSITION: after',
            'BEGIN_BODY',
            'pass',
            'END_BODY',
        ))
        self.assertIn('lines 5, 6', first_message(run))


class MissedOldBlocksNameTheClosestBlock(ForgeCase):

    def run_old_block(self, op_name):
        lines = [
            op_name + ' app.py',
            'BEGIN_OLD',
            '    value = 2',
            '    return value',
            'END_OLD',
        ]
        if op_name == 'REPLACE':
            lines += ['BEGIN_NEW', '    value = 3', '    return value', 'END_NEW']
        return self.run_bundle(bundle(*lines))

    def assert_points_at_the_drift(self, run):
        self.assertEqual(self.statuses(run), ['FAILED_NOT_FOUND'])
        message = first_message(run)
        self.assertIn('Closest: lines 2-3', message)
        self.assertIn("'    value = 2'", message)
        self.assertIn("'    value = 1'", message)
        self.assertEqual(self.get('app.py'), SOURCE)

    def test_replace_miss_names_the_closest_block(self):
        self.put('app.py', SOURCE)
        self.assert_points_at_the_drift(self.run_old_block('REPLACE'))

    def test_delete_miss_names_the_closest_block(self):
        self.put('app.py', SOURCE)
        self.assert_points_at_the_drift(self.run_old_block('DELETE'))


class NearMatchHelpers(unittest.TestCase):

    def test_unrelated_text_is_not_offered_as_close(self):
        message = describe_closest('alpha\nbeta\n', 'zzzzzzzzzzzz')
        self.assertIn('No block in the file is close', message)

    def test_closest_block_finds_the_drifted_lines(self):
        found = closest_block(SOURCE, '    value = 2\n    return value')
        self.assertEqual((found['start'], found['end']), (2, 3))
        self.assertEqual(found['difference'][0], 2)

    def test_line_numbers_are_listed_compactly(self):
        self.assertEqual(format_line_numbers([3]), 'line 3')
        self.assertEqual(
            format_line_numbers(range(1, 11)),
            'lines 1, 2, 3, 4, 5, 6, 7, 8 (+2 more)',
        )


class EarliestNamedHintWins(unittest.TestCase):

    def test_message_subject_beats_table_order(self):
        from forge.core.hinting import _matching_hints
        hints = {
            'line': {'message': 'LINE HINT'},
            'anchor': {'message': 'ANCHOR HINT'},
        }
        rendered = _matching_hints(
            hints,
            'skipped_anchor_mismatch anchor matched 2 times, expected 1 (lines 2, 7)',
            1,
        )
        self.assertEqual(len(rendered), 1)
        self.assertIn('ANCHOR HINT', rendered[0])


if __name__ == '__main__':
    unittest.main()