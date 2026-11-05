# -*- coding: utf-8 -*-
"""FORGE rerun <stamp>: replay a repaired FAILED_PARSE bundle.

A bundle refused at parse time ran nothing. Its stored bundle.txt can be
repaired in place, then replayed as a fresh run with its own stamp.
"""

import os
import unittest

from forge_case import ForgeCase, bundle, forge


class Rerun(ForgeCase):

    def run_stored(self, text):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=True,
        )

    def stored_bundle_path(self, run):
        path = os.path.join(run.get('artifact_dir') or '', 'bundle.txt')
        self.assertTrue(os.path.isfile(path), run.get('artifact_dir'))
        return path

    def errors(self, run):
        return '\n'.join(run.get('errors') or [])

    def broken_run(self):
        """A stored run refused for a missing end marker."""
        run = self.run_stored(
            bundle(
                'WRITE fixed.txt',
                'BEGIN_BODY',
                'hello',
            )
        )
        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertFalse(self.exists('fixed.txt'))
        return run

    def test_repaired_bundle_reruns_as_a_new_run(self):
        broken = self.broken_run()
        path = self.stored_bundle_path(broken)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write('\nEND_BODY')

        rerun = self.run_stored('FORGE rerun ' + broken['stamp'])

        self.assertEqual(self.statuses(rerun), ['APPLIED'], rerun)
        self.assertEqual(self.get('fixed.txt'), 'hello')
        self.assertEqual(rerun.get('rerun_of'), broken['stamp'])
        self.assertNotEqual(rerun.get('stamp'), broken['stamp'])
        self.assertIn('Rerun of: ' + broken['stamp'], rerun.get('packet'))

    def test_failed_parse_packet_names_the_repair(self):
        broken = self.broken_run()

        packet = broken.get('packet') or ''
        self.assertIn('Repair: REPLACE ', packet)
        self.assertIn('bundle.txt', packet)
        self.assertIn('FORGE rerun ' + broken['stamp'], packet)

    def test_failed_rerun_points_repair_at_the_original(self):
        broken = self.broken_run()

        rerun = self.run_stored('FORGE rerun ' + broken['stamp'])

        self.assertEqual(rerun.get('status'), 'FAILED_PARSE', rerun)
        self.assertIn(
            'FORGE rerun ' + broken['stamp'],
            rerun.get('repair') or '',
        )

    def test_rerun_of_a_rerun_names_the_original(self):
        broken = self.broken_run()
        first = self.run_stored('FORGE rerun ' + broken['stamp'])

        second = self.run_stored('FORGE rerun ' + first['stamp'])

        self.assertEqual(second.get('status'), 'FAILED_PARSE', second)
        self.assertEqual(second.get('results'), [])
        self.assertIn(
            'Repair the bundle of run ' + broken['stamp'],
            self.errors(second),
        )

    def test_applied_run_is_not_replayed(self):
        applied = self.run_stored(
            bundle(
                'WRITE once.txt',
                'BEGIN_BODY',
                'one',
                'END_BODY',
            )
        )
        self.assertEqual(applied.get('status'), 'APPLIED', applied)
        os.remove(os.path.join(self.project_root, 'once.txt'))

        rerun = self.run_stored('FORGE rerun ' + applied['stamp'])

        self.assertEqual(rerun.get('status'), 'FAILED_PARSE', rerun)
        self.assertIn('replays only FAILED_PARSE', self.errors(rerun))
        self.assertFalse(self.exists('once.txt'))

    def test_refused_rerun_offers_no_repair(self):
        run = self.run_stored('FORGE rerun 19990101_000000')

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertFalse(run.get('repair'), run.get('repair'))
        self.assertNotIn('Repair:', run.get('packet') or '')

    def test_unknown_stamp_is_refused(self):
        run = self.run_bundle('FORGE rerun 19990101_000000')

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('No stored bundle', self.errors(run))

    def test_missing_stamp_is_refused(self):
        run = self.run_bundle('FORGE rerun')

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('needs a run stamp', self.errors(run))

    def test_rerun_mixed_with_other_ops_is_refused(self):
        run = self.run_bundle(
            bundle(
                'FORGE rerun 19990101_000000',
                'WRITE never.txt',
                'BEGIN_BODY',
                'no',
                'END_BODY',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('must be the whole bundle', self.errors(run))
        self.assertFalse(self.exists('never.txt'))


if __name__ == '__main__':
    unittest.main()
