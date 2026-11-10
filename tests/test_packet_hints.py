# -*- coding: utf-8 -*-
"""
The packet's FAILURE section: each failure explained once.

A failed run used to state the same explanation under Errors, in the Ops
line, in a hint and again in the preview, and every skipped op repeated
the reason it was skipped. The structured packet gives the explanation one
home, takes only the fix steps from the op's hint, and names skipped ops
by number.
"""

import unittest

from forge_case import ForgeCase, bundle
from forge.core.presentation.standard import render_standard
from forge.core.protocol.packet import format_packet


RUN_FAILURE = 'Script exited with code 1'

GENERIC_HINT = '\n'.join([
    'HINT: DELETE failed and no specific recovery hint matched.',
    'WHY: Forge reported: Disk said no',
    'NEXT:',
    '- Read the reported error and current project state before retrying.',
    '- Make the smallest correction that addresses the reported failure.',
    'HELP:',
    'FORGE help DELETE',
])


class FailureSection(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('fail.py', 'print("boom")\nraise SystemExit(1)\n')

    def gated_run_then_writes(self, write_count):
        lines = ['RUN fail.py', 'STOP_ON_FAIL: yes']
        for n in range(write_count):
            lines += ['', 'WRITE out_%d.txt' % n, 'BEGIN_BODY', 'x', 'END_BODY']
        return self.run_bundle(bundle(*lines))

    def test_failure_is_explained_once(self):
        packet = format_packet(self.gated_run_then_writes(4))
        self.assertEqual(packet.count('=== FAILURE ==='), 1)
        self.assertEqual(packet.count(RUN_FAILURE), 1)

    def test_ops_list_names_every_skipped_op_without_a_reason(self):
        packet = format_packet(self.gated_run_then_writes(4))
        for n in range(4):
            self.assertIn('SKIPPED_AFTER_FAILURE | WRITE | out_%d.txt' % n, packet)
        self.assertNotIn('Skipped mutating op', packet)

    def test_skipped_ops_are_named_by_number_under_the_failure(self):
        packet = format_packet(self.gated_run_then_writes(4))
        self.assertIn('ops 2-5.', packet)

    def test_single_skipped_op_is_named(self):
        packet = format_packet(self.gated_run_then_writes(1))
        self.assertIn('op 2.', packet)

    def test_gate_is_named(self):
        packet = format_packet(self.gated_run_then_writes(2))
        self.assertIn('STOP_ON_FAIL gate', packet)

    def test_fix_steps_come_from_the_ops_hint_without_its_examples(self):
        packet = format_packet(self.gated_run_then_writes(2))
        self.assertIn('Fix:', packet)
        self.assertNotIn('HINT:', packet)
        self.assertNotIn('WHY:', packet)
        self.assertNotIn('EXAMPLE:', packet)

    def test_help_points_at_the_failed_op_only(self):
        packet = format_packet(self.gated_run_then_writes(2))
        self.assertIn('Help: FORGE help RUN', packet)
        self.assertNotIn('FORGE help WRITE', packet)

    def test_failed_run_output_is_labelled_with_its_op(self):
        packet = format_packet(self.gated_run_then_writes(1))
        self.assertIn('--- op 1 · RUN fail.py ---', packet)
        self.assertIn('boom', packet)
        self.assertIn('Its output is under OUTPUT, op 1.', packet)

    def test_outcome_line_counts_and_points_at_the_first_failure(self):
        packet = format_packet(self.gated_run_then_writes(2))
        self.assertIn(
            'Outcome: 0 applied · 1 failed · 2 skipped · first failure at '
            'op 1 of 3',
            packet,
        )

    def test_summary_error_count_is_unchanged(self):
        summary = render_standard(self.gated_run_then_writes(4))
        self.assertIn('Errors: 2', summary)

    def test_refused_bundle_says_nothing_ran(self):
        run = self.run_bundle(bundle('REPLCE app.py'))
        packet = run.get('packet') or ''
        self.assertIn('=== FAILURE ===', packet)
        self.assertIn('Nothing ran', packet)
        self.assertIn('(none)', packet)


class QuietSuccess(ForgeCase):

    def test_plain_edit_prints_no_output_or_failure_section(self):
        run = self.run_bundle(
            bundle('WRITE new.txt', 'BEGIN_BODY', 'x', 'END_BODY')
        )
        packet = run.get('packet') or ''
        self.assertIn('=== CHANGED ===', packet)
        self.assertNotIn('=== OUTPUT ===', packet)
        self.assertNotIn('=== FAILURE ===', packet)
        self.assertNotIn('Outcome:', packet)

    def test_read_output_is_labelled_with_its_op(self):
        self.put('notes.txt', 'one\n')
        run = self.run_bundle(bundle('READ notes.txt'))
        self.assertIn('--- op 1 · READ notes.txt ---', run.get('packet') or '')

    def test_ops_line_does_not_repeat_the_target(self):
        run = self.run_bundle(
            bundle('WRITE new.txt', 'BEGIN_BODY', 'x', 'END_BODY')
        )
        ops_line = [
            line for line in (run.get('packet') or '').splitlines()
            if line.startswith('1. ')
        ][0]
        self.assertEqual(ops_line.count('new.txt'), 1, ops_line)


class HintTrimming(unittest.TestCase):

    def packet_for(self, result):
        return format_packet({'status': 'FAILED', 'results': [result]})

    def test_generic_hint_adds_only_the_help_command(self):
        packet = self.packet_for({
            'op': 'DELETE',
            'target': 'a.txt',
            'status': 'FAILED_IO',
            'message': 'Disk said no',
            'hint': GENERIC_HINT,
        })
        self.assertEqual(packet.count('Disk said no'), 1)
        self.assertNotIn('Fix:', packet)
        self.assertIn('Help: FORGE help DELETE', packet)

    def test_traceback_is_shown_with_the_failure(self):
        packet = self.packet_for({
            'op': 'MAP',
            'target': '.',
            'status': 'FAILED_RUNTIME',
            'message': 'ValueError: bad depth',
            'data': {'traceback': 'File "op.py", line 3\nValueError: bad depth'},
        })
        self.assertIn('Traceback (last lines):', packet)
        self.assertIn('File "op.py", line 3', packet)


if __name__ == '__main__':
    unittest.main()