# -*- coding: utf-8 -*-
"""Optional ENV: first line naming the app a bundle is meant for."""

import importlib
import unittest

from forge_case import ForgeCase, bundle

app_identity = importlib.import_module('forge.core.app_identity')
packet = importlib.import_module('forge.core.protocol.packet')


class EnvHeader(ForgeCase):
    """Every test pretends Forge is running in Pythonista."""

    def setUp(self):
        super().setUp()
        self._real_detect_app = app_identity.detect_app
        app_identity.detect_app = lambda: 'pythonista'

    def tearDown(self):
        app_identity.detect_app = self._real_detect_app

    def test_no_header_runs_as_before(self):
        run = self.run_bundle(bundle('FORGE ops'))

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertIsNone(run.get('bundle_env'))
        self.assertIsNone(run.get('env_warning'))
        self.assertEqual(run.get('app'), 'pythonista')

    def test_matching_header_runs_without_warning(self):
        run = self.run_bundle(
            bundle(
                'ENV: pythonista',
                'WRITE marked.txt',
                'BEGIN_BODY',
                'ran',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(self.get('marked.txt'), 'ran')
        self.assertEqual(run.get('bundle_env'), 'pythonista')
        self.assertIsNone(run.get('env_warning'))

    def test_loose_spelling_and_mismatch_warn_but_run(self):
        run = self.run_bundle(
            bundle(
                'env : Python IDE',
                'WRITE elsewhere.txt',
                'BEGIN_BODY',
                'still ran',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(self.get('elsewhere.txt'), 'still ran')
        self.assertEqual(run.get('bundle_env'), 'pythonide')
        warning = run.get('env_warning') or ''
        self.assertIn('pythonide', warning)
        self.assertIn('pythonista', warning)

    def test_unknown_app_warns_but_runs(self):
        run = self.run_bundle(bundle('ENV: notanapp', 'FORGE ops'))

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertIn('not a known app', run.get('env_warning') or '')

    def test_header_inside_a_fence(self):
        run = self.run_bundle(
            bundle(
                '```',
                'ENV: pythonista',
                'FORGE ops',
                '```',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(run.get('bundle_env'), 'pythonista')
        self.assertEqual(run.get('unwrapped_markdown_fence'), 'plain')

    def test_packet_shows_app_and_warning(self):
        plain = packet.format_packet(self.run_bundle(bundle('FORGE ops')))
        self.assertIn('App: pythonista', plain)
        self.assertNotIn('Warning:', plain)

        warned = packet.format_packet(
            self.run_bundle(bundle('ENV: pythonide', 'FORGE ops'))
        )
        self.assertIn('Warning: Bundle is marked ENV: pythonide', warned)


if __name__ == '__main__':
    unittest.main()