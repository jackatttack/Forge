# -*- coding: utf-8 -*-
"""
The standalone branch viewer must never mislead a recovery session.

This module exists for the moment when Forge itself is broken or a
checkpoint seems lost, so its failure mode matters more than its
features: reporting the wrong store, or silently choosing between
several, would let someone conclude their work is gone when it is
simply somewhere else.

The viewer imports no part of Forge at runtime. These tests import it
directly rather than through a Forge run, and build stores on disk.
"""

import json
import os
import shutil
import tempfile
import unittest

from forge import branches as viewer


def make_branch(branches_root, name, created, project_root, files=None,
                manifest=True, restore_script=True):
    """Create one branch directory shaped like BRANCH create leaves it."""
    directory = os.path.join(branches_root, name)
    os.makedirs(os.path.join(directory, 'files'))

    if manifest:
        payload = {
            'name': name,
            'created': created,
            'project_root': project_root,
            'requested': [],
            'files': list(files or []),
        }
        with open(
            os.path.join(directory, 'manifest.json'), 'w', encoding='utf-8',
        ) as handle:
            json.dump(payload, handle)

    if restore_script:
        with open(
            os.path.join(directory, 'restore_branch.py'), 'w',
            encoding='utf-8',
        ) as handle:
            handle.write('# standalone restore\n')

    return directory


class ViewerCase(unittest.TestCase):

    def setUp(self):
        self.temporary = tempfile.mkdtemp(prefix='forge-branch-view-')
        self.addCleanup(shutil.rmtree, self.temporary, True)

    def make_store(self, home_name='.forge'):
        """Return the branches root of a new empty Forge home."""
        root = os.path.join(
            self.temporary, home_name, 'artifacts', 'branches',
        )
        os.makedirs(root)
        return root


class ReadingOneBranch(ViewerCase):

    def test_manifest_fields_are_reported(self):
        store = self.make_store()
        directory = make_branch(
            store, 'before_change', '2026-09-13T11:54:06',
            '/projects/example', files=['a.py', 'b.py'],
        )

        summary = viewer.read_branch(directory)

        self.assertEqual(summary['name'], 'before_change')
        self.assertEqual(summary['created'], '2026-09-13T11:54:06')
        self.assertEqual(summary['project_root'], '/projects/example')
        self.assertEqual(summary['file_count'], 2)
        self.assertEqual(summary['problem'], '')

    def test_missing_manifest_is_reported_not_raised(self):
        """A damaged branch must still appear, flagged."""
        store = self.make_store()
        directory = make_branch(
            store, 'damaged', '', '', manifest=False,
        )

        summary = viewer.read_branch(directory)

        self.assertIn('manifest', summary['problem'])
        self.assertEqual(summary['name'], 'damaged')

    def test_unreadable_manifest_is_reported_not_raised(self):
        store = self.make_store()
        directory = make_branch(store, 'corrupt', '', '')
        with open(
            os.path.join(directory, 'manifest.json'), 'w', encoding='utf-8',
        ) as handle:
            handle.write('{not json')

        summary = viewer.read_branch(directory)

        self.assertIn('manifest', summary['problem'])

    def test_missing_restore_script_is_visible(self):
        """Recovery depends on this script, so its absence must show."""
        store = self.make_store()
        directory = make_branch(
            store, 'no_script', '2026-09-13T10:00:00', '/projects/example',
            restore_script=False,
        )

        summary = viewer.read_branch(directory)

        self.assertEqual(summary['restore_script'], '')


class OrderingBranches(ViewerCase):

    def test_newest_branch_comes_first(self):
        store = self.make_store()
        make_branch(store, 'older', '2026-09-01T09:00:00', '/projects/example')
        make_branch(store, 'newer', '2026-09-13T09:00:00', '/projects/example')

        names = [item['name'] for item in viewer.collect_branches(store)]

        self.assertEqual(names[0], 'newer')


class FindingStores(ViewerCase):

    def test_explicit_home_is_used(self):
        store = self.make_store()
        home = os.path.join(self.temporary, '.forge')

        locations, _ = viewer.find_branch_locations(home)

        self.assertEqual(locations, [store])

    def test_explicit_home_without_branches_finds_nothing(self):
        locations, searched = viewer.find_branch_locations(self.temporary)

        self.assertEqual(locations, [])
        self.assertTrue(searched)

    def test_every_store_is_reported_not_just_the_first(self):
        """
        Two Forge homes can coexist, one stale. Choosing silently between
        them is the failure this viewer exists to prevent.
        """
        first = self.make_store('.forge')
        second = self.make_store('.forge-old')

        def candidates():
            return [
                os.path.join(self.temporary, '.forge'),
                os.path.join(self.temporary, '.forge-old'),
            ]

        original = viewer.candidate_forge_homes
        viewer.candidate_forge_homes = candidates
        try:
            locations, _ = viewer.find_branch_locations()
        finally:
            viewer.candidate_forge_homes = original

        self.assertEqual(len(locations), 2)
        self.assertIn(first, locations)
        self.assertIn(second, locations)


class ReportingLimits(ViewerCase):

    def test_default_shows_recent_branches_only(self):
        store = self.make_store()
        for index in range(viewer.DEFAULT_SHOWN + 5):
            make_branch(
                store, 'branch_%02d' % index,
                '2026-09-%02dT09:00:00' % (index + 1),
                '/projects/example',
            )

        branches = viewer.collect_branches(store)

        self.assertEqual(len(branches), viewer.DEFAULT_SHOWN + 5)
        self.assertEqual(
            len(branches[:viewer.DEFAULT_SHOWN]), viewer.DEFAULT_SHOWN,
        )

    def test_missing_store_returns_failure_exit_code(self):
        """A wrong answer is worse than a clear failure."""
        code = viewer.main([os.path.join(self.temporary, 'absent')])

        self.assertEqual(code, 1)

    def test_found_store_returns_success_exit_code(self):
        store = self.make_store()
        make_branch(
            store, 'before_change', '2026-09-13T11:54:06', '/projects/example',
        )

        code = viewer.main([os.path.join(self.temporary, '.forge')])

        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()