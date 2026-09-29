# -*- coding: utf-8 -*-
"""
The packet's Ops summary and ambiguity hints say what actually happened.

A targetless op (FORGE, MEMORY, GIT) shows its subcommand instead of "?".
An ambiguous REPLACE or DELETE gets advice about repeated OLD blocks, not
only about duplicated definition names.
"""

import unittest

from forge_case import ForgeCase, bundle


class OpSummary(ForgeCase):

    def test_targetless_op_shows_its_subcommand(self):
        run = self.run_bundle(bundle('FORGE ops'))
        self.assertIn('| FORGE | ops ::', run.get('packet') or '')

    def test_targeted_op_still_shows_its_target(self):
        self.put('notes.txt', 'one\n')
        run = self.run_bundle(bundle('READ notes.txt'))
        self.assertIn('| READ | notes.txt ::', run.get('packet') or '')


class AmbiguityHints(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'same\nmiddle\nsame\n')

    def hint_for(self, *lines):
        run = self.run_bundle(bundle(*lines))
        return run['results'][0].get('hint') or ''

    def test_replace_repeated_old_block(self):
        hint = self.hint_for(
            'REPLACE notes.txt',
            'BEGIN_OLD', 'same', 'END_OLD', 'BEGIN_NEW', 'new', 'END_NEW')
        self.assertIn('Repeated OLD block', hint)
        self.assertIn('OCCURRENCE: N', hint)

    def test_delete_repeated_old_block(self):
        hint = self.hint_for('DELETE notes.txt', 'BEGIN_OLD', 'same', 'END_OLD')
        self.assertIn('Add OCCURRENCE: N', hint)


class MultiLineMessages(unittest.TestCase):
    """A multi-line message stays out of the one-line Ops summary."""

    def packet_for(self, result):
        from forge.core.protocol.packet import format_packet
        return format_packet({'status': 'APPLIED', 'results': [result]})

    def test_first_line_in_ops_rest_in_preview(self):
        packet = self.packet_for({
            'op': 'PROJECTS',
            'target': '',
            'args': 'brief demo',
            'status': 'APPLIED',
            'message': 'PROJECT: Demo\nPath: projects/demo\nStatus: active',
        })
        ops, _, preview = packet.partition('=== PREVIEW ===')
        self.assertIn(
            '- APPLIED | PROJECTS | brief demo :: PROJECT: Demo (continued in PREVIEW)',
            ops,
        )
        self.assertNotIn('Path: projects/demo', ops)
        self.assertIn('Path: projects/demo', preview)

    def test_single_line_message_unchanged(self):
        packet = self.packet_for({
            'op': 'READ',
            'target': 'notes.txt',
            'status': 'APPLIED',
            'message': 'Lines 1-4',
            'preview': 'notes.txt [lines 1-4]',
        })
        self.assertIn('- APPLIED | READ | notes.txt :: Lines 1-4\n', packet)
        self.assertNotIn('continued in PREVIEW', packet)


class HintKeyMatching(unittest.TestCase):
    """Hint keys match whole words, not fragments of longer names."""

    def hint_for(self, status, message):
        import types
        from forge.core.hinting import render_hints_for_result
        op = types.SimpleNamespace(
            SPEC={'name': 'INSERT'},
            HINTS={'anchor': {'message': 'Anchor hint.'}},
            HELP={'directives': {}},
        )
        return render_hints_for_result(
            op, {'op': 'INSERT', 'status': status, 'message': message})

    def test_key_inside_a_longer_word_does_not_match(self):
        text = self.hint_for(
            'FAILED_NOT_FOUND', 'Target not found: app.py::AnchorSelection')
        self.assertNotIn('Anchor hint.', text)

    def test_whole_word_matches(self):
        text = self.hint_for('SKIPPED_ANCHOR_MISMATCH', 'ANCHOR: matched 2 times')
        self.assertIn('Anchor hint.', text)

    def test_plural_matches(self):
        text = self.hint_for('FAILED_RUNTIME', 'Both anchors were empty')
        self.assertIn('Anchor hint.', text)


class BareClassTarget(ForgeCase):
    """A bare class name as a :: target says which form resolves."""

    def test_not_found_suggests_the_star_form(self):
        self.put('lab.py', 'class Box:\n    def open(self):\n        return 1\n')
        run = self.run_bundle(bundle('READ lab.py::Box'))
        result = run['results'][0]
        self.assertEqual(result['status'], 'FAILED_NOT_FOUND')
        self.assertIn('::Box.*', result['message'])

    def test_star_form_resolves(self):
        self.put('lab.py', 'class Box:\n    def open(self):\n        return 1\n')
        run = self.run_bundle(bundle('READ lab.py::Box.*'))
        self.assertEqual(run['results'][0]['status'], 'APPLIED')


class RunRows(unittest.TestCase):
    """FORGE runs rows summarise each stored packet."""

    PACKET = '\n'.join([
        '=== FORGE RUN ===',
        'Run: 20260101_000000',
        'Mode: dev',
        'Status: FAILED',
        '',
        'Ops:',
        '- APPLIED | WRITE | notes.txt :: Created file: notes.txt',
        '- Project home is projects/demo.',
        '- FAILED_NOT_FOUND | REPLACE | app.py :: LINES out of range',
        '',
        'Changed files:',
        '- notes.txt — created · 1 lines',
        '',
        'Use DIFF current for compact details.',
    ])

    def row(self, packet):
        from forge.packages.core_ops.forge import op as forge_op
        return forge_op._run_row('20260101_000000', packet)

    def test_row_carries_status_counts_changed_and_first_op(self):
        row = self.row(self.PACKET)
        self.assertEqual(
            row,
            '- 20260101_000000  FAILED  1 applied · 0 skipped · 1 failed'
            '  changed 1 file  first: WRITE notes.txt',
        )

    def test_missing_packet_gives_the_stamp(self):
        self.assertEqual(self.row(''), '- 20260101_000000')


if __name__ == '__main__':
    unittest.main()