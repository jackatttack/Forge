# -*- coding: utf-8 -*-
"""
REVERT must restore a file to the root it was actually written to.

Recovery resolves a recorded relative path against a root. If a write
into a named root were recorded without that root, recovery would
resolve it against project_root instead — the wrong tree. These tests
prove the round trip works and that a damaged record is refused rather
than applied somewhere unintended.
"""

import json
import os
import shutil
import tempfile
import unittest

from forge_case import bundle

import forge
from forge.core import run_storage


class RootRecoveryCase(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.mkdtemp(prefix='forge-root-revert-')
        self.addCleanup(shutil.rmtree, self.temporary, True)

        self.project_root = os.path.join(self.temporary, 'project')
        self.other_root = os.path.join(self.temporary, 'elsewhere')
        self.forge_home = os.path.join(self.temporary, '.forge')

        os.makedirs(self.project_root)
        os.makedirs(self.other_root)
        os.makedirs(self.forge_home)

        with open(
            os.path.join(self.forge_home, 'forge.json'), 'w',
            encoding='utf-8',
        ) as handle:
            json.dump(
                {'config_version': 1, 'roots': {'other': self.other_root}},
                handle,
            )

    def run_bundle(self, text):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=True,
        )

    def statuses(self, run):
        return [
            str(result.get('status') or '')
            for result in (run.get('results') or [])
        ]

    def put(self, root, relative_path, text):
        with open(
            os.path.join(root, relative_path), 'w', encoding='utf-8',
        ) as handle:
            handle.write(text)

    def read(self, root, relative_path):
        with open(
            os.path.join(root, relative_path), 'r', encoding='utf-8',
        ) as handle:
            return handle.read()

    def revert(self, run):
        return self.run_bundle(bundle('REVERT ' + run['stamp']))


class WriteIntoNamedRootIsRecorded(RootRecoveryCase):

    def test_manifest_records_the_root_name_separately(self):
        """The prefix must not be smuggled into the relative path."""
        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'second root content',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')

        manifest, error = run_storage.read_manifest(
            self.project_root,
            run['stamp'],
            environment=run['environment'],
        )

        self.assertIsNone(error)
        entry = manifest['touched'][0]
        self.assertEqual(entry['rel'], 'created.txt')
        self.assertEqual(entry['root'], 'other')

    def test_manifest_records_the_resolved_root_path(self):
        """Recovery must not depend on configuration staying unchanged."""
        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'second root content',
                'END_BODY',
            )
        )

        manifest, error = run_storage.read_manifest(
            self.project_root,
            run['stamp'],
            environment=run['environment'],
        )

        self.assertIsNone(error)
        self.assertEqual(manifest['roots']['other'], self.other_root)

    def test_project_root_write_records_no_root_name(self):
        """The ordinary case must stay exactly as it was."""
        run = self.run_bundle(
            bundle(
                'WRITE ordinary.txt',
                'BEGIN_BODY',
                'project content',
                'END_BODY',
            )
        )

        manifest, error = run_storage.read_manifest(
            self.project_root,
            run['stamp'],
            environment=run['environment'],
        )

        self.assertIsNone(error)
        entry = manifest['touched'][0]
        self.assertEqual(entry['rel'], 'ordinary.txt')
        self.assertEqual(entry['root'], '')


class RevertAcrossRoots(RootRecoveryCase):

    def test_created_file_is_removed_from_the_named_root(self):
        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'second root content',
                'END_BODY',
            )
        )

        self.assertTrue(
            os.path.isfile(os.path.join(self.other_root, 'created.txt'))
        )

        recovery = self.revert(run)

        self.assertEqual(self.statuses(recovery)[0], 'APPLIED')
        self.assertFalse(
            os.path.isfile(os.path.join(self.other_root, 'created.txt'))
        )

    def test_overwritten_file_is_restored_in_the_named_root(self):
        self.put(self.other_root, 'existing.txt', 'original content\n')

        run = self.run_bundle(
            bundle(
                'WRITE other:existing.txt',
                'CONFIRM: overwrite',
                'BEGIN_BODY',
                'replacement content',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')

        recovery = self.revert(run)

        self.assertEqual(self.statuses(recovery)[0], 'APPLIED')
        self.assertEqual(
            self.read(self.other_root, 'existing.txt'),
            'original content\n',
        )

    def test_revert_does_not_touch_the_project_root(self):
        """The wrong-tree failure this whole change exists to prevent."""
        self.put(self.project_root, 'created.txt', 'project file\n')

        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'second root content',
                'END_BODY',
            )
        )

        recovery = self.revert(run)

        self.assertEqual(self.statuses(recovery)[0], 'APPLIED')
        self.assertEqual(
            self.read(self.project_root, 'created.txt'),
            'project file\n',
        )


if __name__ == '__main__':
    unittest.main()