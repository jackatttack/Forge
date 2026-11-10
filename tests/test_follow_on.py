# -*- coding: utf-8 -*-
"""Fix and replay in one bundle.

A bundle may end with FORGE rerun <stamp> or FORGE resume <stamp>. The
operations before it run first; the replay starts only if they applied.
Two stored runs, one packet, and one continuous run for the host.
"""

import os
import unittest

from forge_case import ForgeCase, bundle, forge


RUN_HEADER = '=== FORGE RUN ==='


class FollowOn(ForgeCase):

    def run_stored(self, text, on_event=None):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=True,
            on_event=on_event,
        )

    def errors(self, run):
        return '\n'.join(str(error) for error in run.get('errors') or [])

    def partly_applied_run(self):
        """A stored run: op 1 applies, op 2 fails, op 3 is skipped."""
        self.put('notes.txt', 'alpha\n')
        run = self.run_stored(
            bundle(
                'WRITE one.txt',
                'BEGIN_BODY',
                'one',
                'END_BODY',
                '',
                'REPLACE notes.txt',
                'BEGIN_OLD',
                'beta',
                'END_OLD',
                'BEGIN_NEW',
                'gamma',
                'END_NEW',
                '',
                'WRITE three.txt',
                'BEGIN_BODY',
                'three',
                'END_BODY',
            )
        )
        self.assertEqual(run.get('status'), 'FAILED', run.get('packet'))
        return run

    def fix_and_resume(self, failed, on_event=None):
        return self.run_stored(
            bundle(
                'WRITE notes.txt',
                'CONFIRM: overwrite',
                'BEGIN_BODY',
                'beta',
                'END_BODY',
                '',
                'FORGE resume ' + failed['stamp'],
            ),
            on_event=on_event,
        )

    def test_fix_and_resume_in_one_bundle(self):
        failed = self.partly_applied_run()

        combined = self.fix_and_resume(failed)

        self.assertEqual(combined.get('status'), 'APPLIED', combined.get('packet'))
        self.assertEqual(
            self.statuses(combined),
            ['APPLIED', 'APPLIED', 'APPLIED', 'APPLIED'],
        )
        self.assertEqual(self.get('notes.txt'), 'gamma')
        self.assertEqual(self.get('three.txt'), 'three')

        packet = combined.get('packet') or ''
        self.assertEqual(packet.count(RUN_HEADER), 2, packet)
        self.assertIn('Follow-on: FORGE resume ' + failed['stamp'], packet)
        self.assertIn('Resume of: ' + failed['stamp'], packet)
        self.assertIn('Follows: ', packet)

        chain = combined.get('chain') or []
        self.assertEqual(len(chain), 2)
        self.assertNotEqual(chain[0], chain[1])
        self.assertIn('Runs: ', forge.render_standard(combined))

    def test_follow_on_does_not_start_when_the_fix_fails(self):
        failed = self.partly_applied_run()

        run = self.run_stored(
            bundle(
                'REPLACE notes.txt',
                'BEGIN_OLD',
                'nowhere',
                'END_OLD',
                'BEGIN_NEW',
                'x',
                'END_NEW',
                '',
                'FORGE resume ' + failed['stamp'],
            )
        )

        self.assertEqual(run.get('status'), 'FAILED', run.get('packet'))
        packet = run.get('packet') or ''
        self.assertEqual(packet.count(RUN_HEADER), 1, packet)
        self.assertIn('was not started', packet)
        self.assertFalse(run.get('chain'))
        self.assertFalse(self.exists('three.txt'))

    def test_repaired_bundle_reruns_after_another_operation(self):
        broken = self.run_stored(
            bundle(
                'WRITE fixed.txt',
                'BEGIN_BODY',
                'hello',
            )
        )
        self.assertEqual(broken.get('status'), 'FAILED_PARSE', broken)
        path = os.path.join(broken.get('artifact_dir') or '', 'bundle.txt')
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write('\nEND_BODY')

        combined = self.run_stored(
            bundle(
                'MAP .',
                'DEPTH: 1',
                '',
                'FORGE rerun ' + broken['stamp'],
            )
        )

        self.assertEqual(combined.get('status'), 'APPLIED', combined.get('packet'))
        self.assertEqual(self.get('fixed.txt'), 'hello')
        self.assertIn('Rerun of: ' + broken['stamp'], combined.get('packet'))

    def test_refused_follow_on_is_reported_after_the_applied_fix(self):
        combined = self.run_bundle(
            bundle(
                'ENV: pythonista',
                'MAP .',
                'DEPTH: 1',
                '',
                'FORGE resume 19990101_000000',
            )
        )

        self.assertEqual(combined.get('status'), 'FAILED_PARSE', combined)
        self.assertEqual((combined.get('packet') or '').count(RUN_HEADER), 2)
        self.assertIn('No stored run', self.errors(combined))

    def test_command_before_other_operations_is_still_refused(self):
        run = self.run_bundle(
            bundle(
                'FORGE resume 19990101_000000',
                '',
                'MAP .',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('must be the whole bundle', self.errors(run))

    def test_host_sees_one_continuous_run(self):
        failed = self.partly_applied_run()
        events = []

        combined = self.fix_and_resume(failed, on_event=events.append)

        names = [event.get('event') for event in events]
        self.assertEqual(names.count('run_started'), 1, names)
        self.assertEqual(names.count('run_finished'), 1, names)
        self.assertEqual(names[-1], 'run_finished')

        finished = [
            event for event in events
            if event.get('event') == 'operation_finished'
        ]
        self.assertEqual([event.get('index') for event in finished], [1, 2, 3, 4])
        self.assertEqual(finished[-1].get('total'), 4)

        last = events[-1]
        self.assertEqual(last.get('status'), 'APPLIED')
        self.assertEqual(last.get('result_count'), 4)
        self.assertEqual(last.get('stamp'), combined.get('stamp'))

    def test_host_sees_one_finish_when_the_follow_on_never_starts(self):
        failed = self.partly_applied_run()
        events = []

        self.run_stored(
            bundle(
                'READ missing.txt',
                '',
                'FORGE resume ' + failed['stamp'],
            ),
            on_event=events.append,
        )

        names = [event.get('event') for event in events]
        self.assertEqual(names.count('run_finished'), 1, names)
        self.assertEqual(events[-1].get('status'), 'FAILED')


if __name__ == '__main__':
    unittest.main()