# -*- coding: utf-8 -*-
"""
Pre-flight validation and content-anchored INSERT.

Pre-flight: every op's static validate() runs before any op executes, so a
bundle refused for a directive rule has run nothing (FAILED_PARSE).

INSERT: plain files accept ANCHOR as well as LINE; OCCURRENCE alone selects
a match as it does in REPLACE; the preview shows where the body landed.
"""

import unittest

from forge_case import ForgeCase, bundle


class PreflightValidation(ForgeCase):

    def test_directive_rule_failure_runs_nothing(self):
        """A later op breaking a directive rule must stop earlier ops too."""
        run = self.run_bundle(bundle(
            'WRITE created.txt',
            'BEGIN_BODY',
            'content',
            'END_BODY',
            '',
            'INSERT created.txt',
            'POSITION: after',
            'BEGIN_BODY',
            'new line',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'FAILED_PARSE')
        self.assertEqual(run.get('results') or [], [])
        self.assertFalse(self.exists('created.txt'))
        self.assertTrue(any('INSERT' in e for e in run.get('errors') or []))

    def test_refused_op_gets_a_hint(self):
        run = self.run_bundle(bundle(
            'INSERT notes.txt',
            'LINE: 1',
            'ANCHOR: beta',
            'POSITION: after',
            'BEGIN_BODY',
            'new',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'FAILED_PARSE')
        hints = run.get('parse_hints') or []
        self.assertTrue(hints)
        self.assertEqual(hints[-1]['op'], 'INSERT')


class PlainFileInsert(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'alpha\nbeta\ngamma\n')

    def insert(self, *lines):
        return self.run_bundle(bundle('INSERT notes.txt', *lines))

    def test_anchor_after(self):
        run = self.insert('ANCHOR: beta', 'POSITION: after',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(self.get('notes.txt'), 'alpha\nbeta\nnew\ngamma\n')

    def test_anchor_before(self):
        run = self.insert('ANCHOR: beta', 'POSITION: before',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(self.get('notes.txt'), 'alpha\nnew\nbeta\ngamma\n')

    def test_preview_marks_landed_lines(self):
        run = self.insert('ANCHOR: beta', 'POSITION: after',
                          'BEGIN_BODY', 'new', 'END_BODY')
        preview = run['results'][0]['preview']
        self.assertIn('landed: lines 3-3', preview)
        self.assertIn('> 0003: new', preview)
        self.assertIn('  0002: beta', preview)

    def test_line_still_works(self):
        run = self.insert('LINE: 1', 'POSITION: after',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(self.get('notes.txt'), 'alpha\nnew\nbeta\ngamma\n')

    def test_line_out_of_range_is_a_runtime_failure(self):
        run = self.insert('LINE: 99', 'POSITION: after',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run['results'][0]['status'], 'FAILED_NOT_FOUND')
        self.assertEqual(self.get('notes.txt'), 'alpha\nbeta\ngamma\n')


class AnchorSelection(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'same\nmiddle\nsame\n')

    def insert(self, *lines):
        return self.run_bundle(bundle('INSERT notes.txt', *lines))

    def test_repeated_anchor_is_refused_without_selection(self):
        run = self.insert('ANCHOR: same', 'POSITION: after',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run['results'][0]['status'], 'SKIPPED_ANCHOR_MISMATCH')
        self.assertEqual(self.get('notes.txt'), 'same\nmiddle\nsame\n')

    def test_occurrence_alone_selects_the_match(self):
        run = self.insert('ANCHOR: same', 'POSITION: after', 'OCCURRENCE: 2',
                          'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(self.get('notes.txt'), 'same\nmiddle\nsame\nnew\n')

    def test_expect_still_asserts_the_total(self):
        run = self.insert('ANCHOR: same', 'POSITION: after', 'OCCURRENCE: 1',
                          'EXPECT: 3', 'BEGIN_BODY', 'new', 'END_BODY')
        self.assertEqual(run['results'][0]['status'], 'SKIPPED_ANCHOR_MISMATCH')
        self.assertEqual(self.get('notes.txt'), 'same\nmiddle\nsame\n')

    def test_ast_occurrence_alone_selects_the_match(self):
        self.put('lab.py', (
            'def main():\n'
            '    print("same")\n'
            '    if True:\n'
            '        print("same")\n'
            '    return 0\n'
        ))
        run = self.run_bundle(bundle(
            'INSERT lab.py::main',
            'ANCHOR: print("same")',
            'POSITION: after',
            'OCCURRENCE: 2',
            'BEGIN_BODY',
            'print("after")',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertIn(
            '        print("same")\n        print("after")\n',
            self.get('lab.py'),
        )


class NoTrailingNewline(ForgeCase):
    """Inserting after an unterminated last line must not join the lines."""

    def test_plain_insert_after_last_line(self):
        self.put('notes.txt', 'alpha\nbeta')
        run = self.run_bundle(bundle(
            'INSERT notes.txt',
            'ANCHOR: beta',
            'POSITION: after',
            'BEGIN_BODY',
            'new',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(self.get('notes.txt'), 'alpha\nbeta\nnew\n')

    def test_ast_sibling_after_last_function(self):
        self.put('lab.py', 'def a():\n    return 1')
        run = self.run_bundle(bundle(
            'INSERT lab.py::a',
            'POSITION: after',
            'BEGIN_BODY',
            'def b():',
            '    return 2',
            'END_BODY',
        ))
        self.assertEqual(run.get('status'), 'APPLIED')
        self.assertEqual(
            self.get('lab.py'),
            'def a():\n    return 1\n\ndef b():\n    return 2\n',
        )


if __name__ == '__main__':
    unittest.main()