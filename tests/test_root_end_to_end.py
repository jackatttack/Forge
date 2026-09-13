# -*- coding: utf-8 -*-
"""
A root configured in forge.json must actually reach a running bundle.

Every other roots test builds its context by hand, so all of them would
still pass if the wiring between configuration, the standard host, the
environment and path resolution were broken. This module runs real
bundles against a real config file instead, which is the only way to
prove the whole chain.
"""

import json
import os
import shutil
import tempfile
import unittest

from forge_case import bundle

import forge


class RootBundleCase(unittest.TestCase):
    """A project root, a separate second root, and a written forge.json."""

    def setUp(self):
        self.temporary = tempfile.mkdtemp(prefix='forge-roots-e2e-')
        self.addCleanup(shutil.rmtree, self.temporary, True)

        self.project_root = os.path.join(self.temporary, 'project')
        self.other_root = os.path.join(self.temporary, 'elsewhere')
        self.forge_home = os.path.join(self.temporary, '.forge')

        os.makedirs(self.project_root)
        os.makedirs(self.other_root)
        os.makedirs(self.forge_home)

        self.write_config({'other': self.other_root})

    def write_config(self, roots):
        payload = {'config_version': 1, 'roots': roots}
        with open(
            os.path.join(self.forge_home, 'forge.json'), 'w',
            encoding='utf-8',
        ) as handle:
            json.dump(payload, handle)

    def run_bundle(self, text):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=False,
        )

    def statuses(self, run):
        return [
            str(result.get('status') or '')
            for result in (run.get('results') or [])
        ]

    def put(self, root, relative_path, text):
        path = os.path.join(root, relative_path)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def read(self, root, relative_path):
        with open(
            os.path.join(root, relative_path), 'r', encoding='utf-8',
        ) as handle:
            return handle.read()


class ConfiguredRootReachesTheBundle(RootBundleCase):

    def test_write_lands_in_the_named_root(self):
        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'hello from the second root',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertTrue(
            os.path.isfile(os.path.join(self.other_root, 'created.txt'))
        )
        self.assertFalse(
            os.path.isfile(os.path.join(self.project_root, 'created.txt'))
        )

    def test_read_finds_a_file_in_the_named_root(self):
        self.put(self.other_root, 'notes.txt', 'second root content\n')

        run = self.run_bundle(
            bundle('READ other:notes.txt')
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')

    def test_unprefixed_write_still_lands_in_the_project_root(self):
        """The default must be completely unaffected by this feature."""
        run = self.run_bundle(
            bundle(
                'WRITE ordinary.txt',
                'BEGIN_BODY',
                'project content',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.read(self.project_root, 'ordinary.txt'),
                         'project content')
        self.assertFalse(
            os.path.isfile(os.path.join(self.other_root, 'ordinary.txt'))
        )

    def test_copy_moves_content_between_roots(self):
        """Cross-root COPY is the reason roots are per-path, not per-run."""
        self.put(self.other_root, 'source.txt', 'copied across roots\n')

        run = self.run_bundle(
            bundle(
                'COPY other:source.txt',
                'TO: imported.txt',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.read(self.project_root, 'imported.txt'),
                         'copied across roots\n')

    def test_unknown_root_fails_the_operation(self):
        run = self.run_bundle(
            bundle(
                'WRITE absent:created.txt',
                'BEGIN_BODY',
                'should not be written',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')

    def test_no_configured_roots_means_prefixes_fail(self):
        """Without configuration the feature must be inert, not partial."""
        self.write_config({})

        run = self.run_bundle(
            bundle(
                'WRITE other:created.txt',
                'BEGIN_BODY',
                'should not be written',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')


if __name__ == '__main__':
    unittest.main()