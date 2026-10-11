# -*- coding: utf-8 -*-
"""Binary reporting must stay compact, root-aware and sensitive to drift."""

import os

from test_copy_move import TransferCase


class BinaryDiffTests(TransferCase):
    def test_current_move_keeps_same_relative_path_in_two_roots(self):
        self.put(self.project_root, 'art.png', b'\x89PNG\xff')
        run = self.run_bundle(
            'MOVE art.png', 'TO: other:art.png', '', 'DIFF current',
        )
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        preview = self.last(run)['preview']
        self.assertIn('2 touched file(s)', preview)
        self.assertIn('\nart.png\n', preview)
        self.assertIn('\nother:art.png\n', preview)
        self.assertEqual(preview.count('drift: no'), 2)
        self.assertIn('deleted by run', preview)
        self.assertIn('created by run', preview)
        self.assertIn('SHA-256', preview)

    def test_stored_diff_detects_binary_drift_in_named_root(self):
        self.put(self.project_root, 'art', b'\xfforiginal')
        original = self.run_bundle('COPY art', 'TO: other:art')
        self.put(self.other_root, 'art', b'\xffchanged')
        run = self.run_bundle('DIFF ' + original['stamp'], 'MODE: full')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertIn('other:art', self.last(run)['preview'])
        self.assertIn('drift: yes', self.last(run)['preview'])
        self.assertIn('current SHA-256', self.last(run)['preview'])

    def test_binary_packet_has_no_payload_or_fake_line_counts(self):
        self.put(self.project_root, 'art', bytes(range(256)) * 10000)
        run = self.run_bundle('COPY art', 'TO: copied', '', 'DIFF current')
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertIn('2560000 bytes', run['packet'])
        self.assertLess(len(run['packet']), 10000)
        self.assertNotIn("b'\\x", run['packet'])

    def test_text_transfer_retains_full_line_diff(self):
        self.put(self.project_root, 'source', 'new\r\n')
        self.put(self.project_root, 'target', 'old\r\n')
        run = self.run_bundle(
            'COPY source', 'TO: target', 'OVERWRITE: yes',
            '', 'DIFF current', 'MODE: full',
        )
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        preview = self.last(run)['preview']
        self.assertIn('old', preview)
        self.assertIn('new', preview)
        self.assertIn('drift: no', preview)
        self.assertNotIn('binary/large file', preview)

    def test_repeated_transfer_reports_original_and_final_state(self):
        self.put(self.project_root, 'one', b'\xffone')
        self.put(self.project_root, 'two', b'\xfftwo')
        self.put(self.project_root, 'target', b'\xfforiginal')
        run = self.run_bundle(
            'COPY one', 'TO: target', 'OVERWRITE: yes',
            '', 'COPY two', 'TO: target', 'OVERWRITE: yes',
            '', 'DIFF current',
        )
        self.assertEqual(self.last(run)['status'], 'APPLIED')
        self.assertIn('1 touched file(s)', self.last(run)['preview'])
        self.assertIn('drift: no', self.last(run)['preview'])
        recovery = self.revert(run)
        self.assertEqual(self.last(recovery)['status'], 'APPLIED')
        with open(os.path.join(self.project_root, 'target'), 'rb') as handle:
            self.assertEqual(handle.read(), b'\xfforiginal')