# -*- coding: utf-8 -*-
"""
Failure gating for extension operations.

An extension op that does not declare a policy must be treated as
effectful: skipped after an earlier failure, and stopping later effects
when it fails itself. forge.core.operation_policy fails closed this way.

Subcommand effects are checked through a real run with BRANCH: list is a
read and still runs after a failure, create changes Forge state and is
skipped.
"""

import os
import unittest

from forge_case import ForgeCase, bundle


PROBE_OP_SOURCE = '''# -*- coding: utf-8 -*-
"""GATEPROBE test fixture: writes its target file to show that it ran.

A target starting with 'fail' makes the op fail without writing.
It declares no execution policy, like most personal extension ops.
"""

from forge.core.file_safety import safe_target


SPEC = {
    'name': 'GATEPROBE',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set([]),
    'required_directives': set([]),
}


def validate(parsed_op):
    if not (parsed_op.get('target') or '').strip():
        return ['GATEPROBE requires a target']
    return []


def execute(ctx, parsed_op, result):
    target = (parsed_op.get('target') or '').strip()
    if target.startswith('fail'):
        result['status'] = 'FAILED_RUNTIME'
        result['message'] = 'GATEPROBE failed on purpose'
        return
    root, abs_path, err = safe_target(ctx, target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return
    with open(abs_path, 'w') as handle:
        handle.write('ran')
    result['status'] = 'APPLIED'
    result['message'] = 'GATEPROBE wrote ' + target
'''


PROBE_MANIFEST_SOURCE = '''# -*- coding: utf-8 -*-

MANIFEST = {
    'name': 'gateprobe',
    'version': '0.1.0',
    'op': 'GATEPROBE',
    'kind': 'custom-op',
    'summary': 'Test fixture for extension failure gating.',
}
'''


class ExtensionFailureGating(ForgeCase):

    def setUp(self):
        super().setUp()
        self.install_probe_op()
        self.put('notes.txt', 'original\n')

    def install_probe_op(self):
        """Put GATEPROBE in this test's own trusted ops folder."""
        folder = os.path.join(self.forge_home, 'ops', 'gateprobe')
        os.makedirs(folder)
        files = {
            '__init__.py': '# GATEPROBE test fixture.\n',
            'op.py': PROBE_OP_SOURCE,
            'manifest.py': PROBE_MANIFEST_SOURCE,
        }
        for name, source in files.items():
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as handle:
                handle.write(source)

    def refused_write(self):
        """A WRITE over existing content without CONFIRM: always refused."""
        return ['WRITE notes.txt', 'BEGIN_BODY', 'replacement', 'END_BODY']

    def test_probe_op_loads_and_runs(self):
        """Guard: without this, the gap tests could fail for the wrong reason."""
        run = self.run_bundle(bundle('GATEPROBE marker.txt'))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertTrue(self.exists('marker.txt'))


    def test_extension_op_is_skipped_after_a_failed_write(self):
        run = self.run_bundle(
            bundle(*(self.refused_write() + ['', 'GATEPROBE marker.txt']))
        )
        statuses = self.statuses(run)
        self.assertNotEqual(statuses[0], 'APPLIED')
        self.assertEqual(statuses[1], 'SKIPPED_AFTER_FAILURE')
        self.assertFalse(self.exists('marker.txt'))


    def test_failed_extension_op_stops_a_later_write(self):
        run = self.run_bundle(
            bundle(
                'GATEPROBE fail_marker.txt',
                '',
                'WRITE after.txt',
                'BEGIN_BODY',
                'written',
                'END_BODY',
            )
        )
        statuses = self.statuses(run)
        self.assertEqual(statuses[0], 'FAILED_RUNTIME')
        self.assertEqual(statuses[1], 'SKIPPED_AFTER_FAILURE')
        self.assertFalse(self.exists('after.txt'))


class SubcommandEffects(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('notes.txt', 'original\n')

    def after_refused_write(self, *lines):
        refused = ['WRITE notes.txt', 'BEGIN_BODY', 'replacement', 'END_BODY', '']
        return self.run_bundle(bundle(*(refused + list(lines))))

    def test_branch_list_still_runs_after_a_failure(self):
        run = self.after_refused_write('BRANCH list')
        self.assertEqual(self.statuses(run)[1], 'APPLIED')

    def test_branch_create_is_skipped_after_a_failure(self):
        run = self.after_refused_write(
            'BRANCH create checkpoint', 'BEGIN_BODY', 'notes.txt', 'END_BODY')
        self.assertEqual(self.statuses(run)[1], 'SKIPPED_AFTER_FAILURE')


if __name__ == '__main__':
    unittest.main(verbosity=2)