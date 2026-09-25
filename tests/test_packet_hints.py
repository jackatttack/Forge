# -*- coding: utf-8 -*-
"""
Packet hints: ops skipped after one failure share a single hint block.
"""

import unittest

from forge_case import ForgeCase, bundle
from forge.core.presentation.standard import render_standard
from forge.core.protocol.packet import format_packet


SKIP_HINT = 'Skipped because an earlier operation in this bundle failed.'
RUN_FAILURE_HINT = 'The script exited with a non-zero code.'


class SkippedAfterFailureHints(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('fail.py', 'raise SystemExit(1)\n')

    def gated_run_then_writes(self, write_count):
        lines = ['RUN fail.py', 'STOP_ON_FAIL: yes']
        for n in range(write_count):
            lines += ['', 'WRITE out_%d.txt' % n, 'BEGIN_BODY', 'x', 'END_BODY']
        return self.run_bundle(bundle(*lines))

    def test_many_skips_share_one_hint(self):
        run = self.gated_run_then_writes(4)
        packet = format_packet(run)
        self.assertEqual(self.statuses(run).count('SKIPPED_AFTER_FAILURE'), 4)
        self.assertEqual(packet.count(SKIP_HINT), 1)
        self.assertIn('4 ops skipped (first: WRITE out_0.txt', packet)

    def test_ops_list_still_names_every_skipped_op(self):
        packet = format_packet(self.gated_run_then_writes(4))
        for n in range(4):
            self.assertIn('SKIPPED_AFTER_FAILURE | WRITE | out_%d.txt' % n, packet)

    def test_the_failure_keeps_its_own_hint(self):
        packet = format_packet(self.gated_run_then_writes(4))
        self.assertEqual(packet.count(RUN_FAILURE_HINT), 1)
        self.assertLess(packet.index(RUN_FAILURE_HINT), packet.index(SKIP_HINT))

    def test_single_skip_keeps_the_per_op_hint(self):
        packet = format_packet(self.gated_run_then_writes(1))
        self.assertEqual(packet.count(SKIP_HINT), 1)
        self.assertNotIn('ops skipped', packet)

    def test_skip_errors_merge_into_one_line(self):
        packet = format_packet(self.gated_run_then_writes(4))
        self.assertIn('- FAILED_RUNTIME | RUN', packet)
        self.assertIn('- SKIPPED_AFTER_FAILURE | 4 ops :: ', packet)
        self.assertNotIn('- SKIPPED_AFTER_FAILURE | WRITE ::', packet)

    def test_single_skip_error_is_unchanged(self):
        packet = format_packet(self.gated_run_then_writes(1))
        self.assertIn('- SKIPPED_AFTER_FAILURE | WRITE ::', packet)

    def test_summary_error_count_matches_the_errors_list(self):
        summary = render_standard(self.gated_run_then_writes(4))
        self.assertIn('Errors: 2', summary)


if __name__ == '__main__':
    unittest.main()