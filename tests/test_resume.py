# -*- coding: utf-8 -*-
"""FORGE resume <stamp>: carry on a partly applied run.

A bundle that fails part-way leaves earlier operations applied and later
ones skipped. Resume replays the stored bundle from the first operation
that did not apply, without running the applied ones again.
"""

import os
import unittest

from forge_case import ForgeCase, bundle, forge

from forge.core.file_versions import file_version


class Resume(ForgeCase):

    def run_stored(self, text):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=True,
        )

    def errors(self, run):
        return '\n'.join(str(error) for error in run.get('errors') or [])

    def edit_stored_bundle(self, run, old, new):
        path = os.path.join(run.get('artifact_dir') or '', 'bundle.txt')
        with open(path, 'r', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn(old, text)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text.replace(old, new))

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
        self.assertEqual(
            self.statuses(run),
            ['APPLIED', 'FAILED_NOT_FOUND', 'SKIPPED_AFTER_FAILURE'],
            run.get('packet'),
        )
        return run

    def test_failed_packet_names_the_resume(self):
        failed = self.partly_applied_run()

        packet = failed.get('packet') or ''
        self.assertIn('Resume: FORGE resume ' + failed['stamp'], packet)
        self.assertIn('op 2 of 3', packet)
        self.assertIn('bundle.txt', packet)

    def test_resume_after_fixing_the_project(self):
        failed = self.partly_applied_run()
        os.remove(os.path.join(self.project_root, 'one.txt'))
        self.put('notes.txt', 'beta\n')

        resumed = self.run_stored('FORGE resume ' + failed['stamp'])

        self.assertEqual(
            self.statuses(resumed),
            ['APPLIED', 'APPLIED', 'APPLIED'],
            resumed.get('packet'),
        )
        self.assertEqual(self.get('notes.txt'), 'gamma\n')
        self.assertEqual(self.get('three.txt'), 'three')
        # Op 1 was carried over, not run: the file removed above stays gone.
        self.assertFalse(self.exists('one.txt'))
        self.assertIn('not run again', resumed['results'][0]['message'])
        self.assertIn('Resume of: ' + failed['stamp'], resumed.get('packet'))
        self.assertNotEqual(resumed.get('stamp'), failed['stamp'])

    def test_resume_after_repairing_the_stored_bundle(self):
        failed = self.partly_applied_run()
        self.edit_stored_bundle(
            failed, 'BEGIN_OLD\nbeta\n', 'BEGIN_OLD\nalpha\n',
        )

        resumed = self.run_stored('FORGE resume ' + failed['stamp'])

        self.assertEqual(
            self.statuses(resumed),
            ['APPLIED', 'APPLIED', 'APPLIED'],
            resumed.get('packet'),
        )
        self.assertEqual(self.get('notes.txt'), 'gamma\n')

    def test_changed_applied_operation_is_refused(self):
        failed = self.partly_applied_run()
        self.edit_stored_bundle(
            failed, 'BEGIN_BODY\none\n', 'BEGIN_BODY\nchanged\n',
        )
        self.put('notes.txt', 'beta\n')

        resumed = self.run_stored('FORGE resume ' + failed['stamp'])

        self.assertEqual(resumed.get('status'), 'FAILED_PARSE', resumed)
        self.assertEqual(resumed.get('results') or [], [])
        self.assertIn('already applied', self.errors(resumed))
        self.assertFalse(self.exists('three.txt'))
        self.assertEqual(self.get('notes.txt'), 'beta\n')

    def test_resumed_run_that_fails_again_can_be_resumed(self):
        failed = self.partly_applied_run()

        second = self.run_stored('FORGE resume ' + failed['stamp'])
        self.assertEqual(
            self.statuses(second),
            ['APPLIED', 'FAILED_NOT_FOUND', 'SKIPPED_AFTER_FAILURE'],
            second.get('packet'),
        )
        self.assertIn(
            'Resume: FORGE resume ' + second['stamp'],
            second.get('packet'),
        )

        self.put('notes.txt', 'beta\n')
        third = self.run_stored('FORGE resume ' + second['stamp'])

        self.assertEqual(
            self.statuses(third),
            ['APPLIED', 'APPLIED', 'APPLIED'],
            third.get('packet'),
        )
        self.assertEqual(self.get('notes.txt'), 'gamma\n')
        # The carried op still names the run that really applied it.
        self.assertIn(failed['stamp'], third['results'][0]['message'])

    def test_applied_run_is_not_resumed(self):
        applied = self.run_stored(
            bundle(
                'WRITE once.txt',
                'BEGIN_BODY',
                'one',
                'END_BODY',
            )
        )
        self.assertEqual(applied.get('status'), 'APPLIED', applied)

        resumed = self.run_stored('FORGE resume ' + applied['stamp'])

        self.assertEqual(resumed.get('status'), 'FAILED_PARSE', resumed)
        self.assertIn('carries on only FAILED runs', self.errors(resumed))

    def test_parse_failed_run_is_sent_to_rerun(self):
        broken = self.run_stored(
            bundle(
                'WRITE fixed.txt',
                'BEGIN_BODY',
                'hello',
            )
        )
        self.assertEqual(broken.get('status'), 'FAILED_PARSE', broken)

        resumed = self.run_stored('FORGE resume ' + broken['stamp'])

        self.assertEqual(resumed.get('status'), 'FAILED_PARSE', resumed)
        self.assertIn('FORGE rerun ' + broken['stamp'], self.errors(resumed))

    def test_run_that_carried_on_after_a_failure_is_refused(self):
        carried_on = self.run_stored(
            bundle(
                'READ missing.txt',
                '',
                'WRITE after.txt',
                'BEGIN_BODY',
                'after',
                'END_BODY',
            )
        )
        self.assertEqual(carried_on.get('status'), 'FAILED', carried_on)
        self.assertNotIn('Resume:', carried_on.get('packet') or '')

        resumed = self.run_stored('FORGE resume ' + carried_on['stamp'])

        self.assertEqual(resumed.get('status'), 'FAILED_PARSE', resumed)
        self.assertIn('cannot be resumed', self.errors(resumed))

    def test_failed_read_alone_offers_no_resume(self):
        run = self.run_stored('READ missing.txt')

        self.assertEqual(run.get('status'), 'FAILED', run)
        self.assertNotIn('Resume:', run.get('packet') or '')

    def test_unknown_stamp_is_refused(self):
        run = self.run_bundle('FORGE resume 19990101_000000')

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('No stored run', self.errors(run))

    def test_missing_stamp_is_refused(self):
        run = self.run_bundle('FORGE resume')

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('needs a run stamp', self.errors(run))

    def test_resume_mixed_with_other_ops_is_refused(self):
        run = self.run_bundle(
            bundle(
                'FORGE resume 19990101_000000',
                'WRITE never.txt',
                'BEGIN_BODY',
                'no',
                'END_BODY',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('must be the whole bundle', self.errors(run))
        self.assertFalse(self.exists('never.txt'))


class ResumeWithPins(Resume):

    def pinned_run(self):
        """Ops 1 and 3 pin notes.txt at the version read before the bundle;
        op 2 fails, so op 3 is skipped after op 1 has changed the file."""
        path = self.put('notes.txt', 'alpha\nbeta\n')
        self.put('other.txt', 'nothing here\n')
        pin = 'IF_VERSION: ' + file_version(path)
        run = self.run_stored(
            bundle(
                'REPLACE notes.txt',
                pin,
                'BEGIN_OLD',
                'alpha',
                'END_OLD',
                'BEGIN_NEW',
                'one',
                'END_NEW',
                '',
                'REPLACE other.txt',
                'BEGIN_OLD',
                'needle',
                'END_OLD',
                'BEGIN_NEW',
                'found',
                'END_NEW',
                '',
                'REPLACE notes.txt',
                pin,
                'BEGIN_OLD',
                'beta',
                'END_OLD',
                'BEGIN_NEW',
                'two',
                'END_NEW',
            )
        )
        self.assertEqual(
            self.statuses(run),
            ['APPLIED', 'FAILED_NOT_FOUND', 'SKIPPED_AFTER_FAILURE'],
            run.get('packet'),
        )
        return run

    def test_pin_shared_with_an_applied_edit_still_passes(self):
        failed = self.pinned_run()
        self.put('other.txt', 'needle\n')

        resumed = self.run_stored('FORGE resume ' + failed['stamp'])

        self.assertEqual(
            self.statuses(resumed),
            ['APPLIED', 'APPLIED', 'APPLIED'],
            resumed.get('packet'),
        )
        self.assertEqual(self.get('notes.txt'), 'one\ntwo\n')

    def test_pin_is_stale_when_the_file_changed_in_between(self):
        failed = self.pinned_run()
        self.put('other.txt', 'needle\n')
        self.put('notes.txt', 'one\nbeta\nedited by hand\n')

        resumed = self.run_stored('FORGE resume ' + failed['stamp'])

        self.assertEqual(
            self.statuses(resumed),
            ['APPLIED', 'APPLIED', 'SKIPPED_STALE_READ'],
            resumed.get('packet'),
        )
        self.assertEqual(self.get('notes.txt'), 'one\nbeta\nedited by hand\n')


if __name__ == '__main__':
    unittest.main()