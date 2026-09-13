# -*- coding: utf-8 -*-
"""
Named roots let one bundle address a second configured filesystem root.

The default must stay exactly as it was: a path with no prefix resolves
against project_root. A prefixed path resolves against its configured
root, and an unknown prefix must fail loudly rather than quietly writing
into the wrong tree.
"""

import unittest

from forge_case import ForgeCase

from forge.core.file_safety import (
    resolve_root,
    safe_target,
    split_root_prefix,
)


class SplitRootPrefix(unittest.TestCase):

    def test_plain_path_has_no_prefix(self):
        self.assertEqual(
            split_root_prefix('projects/app.py'),
            (None, 'projects/app.py'),
        )

    def test_named_prefix_is_split(self):
        self.assertEqual(
            split_root_prefix('icloud:tools/patcher.py'),
            ('icloud', 'tools/patcher.py'),
        )

    def test_separator_inside_a_segment_is_not_a_prefix(self):
        """Only a leading bare name counts, never a colon deeper in the path."""
        self.assertEqual(
            split_root_prefix('notes/a:b.txt'),
            (None, 'notes/a:b.txt'),
        )

    def test_bare_root_name_resolves_to_the_root_itself(self):
        self.assertEqual(
            split_root_prefix('icloud:'),
            ('icloud', ''),
        )


class ResolveRootAgainstContext(ForgeCase):

    def context(self, roots=None):
        """Build a minimal ctx carrying an environment, as ops receive."""
        environment = {
            'project_root': self.project_root,
            'forge_home': self.forge_home,
        }

        if roots is not None:
            environment['roots'] = roots

        return {'environment': environment}

    def test_unprefixed_path_uses_project_root(self):
        root, relative, error = resolve_root(
            self.context(), 'projects/app.py',
        )

        self.assertIsNone(error)
        self.assertEqual(root, self.project_root)
        self.assertEqual(relative, 'projects/app.py')

    def test_unprefixed_path_works_without_any_roots_configured(self):
        """The common case must not require configuration to exist."""
        root, relative, error = resolve_root(self.context(), 'app.py')

        self.assertIsNone(error)
        self.assertEqual(root, self.project_root)

    def test_named_prefix_uses_the_configured_root(self):
        root, relative, error = resolve_root(
            self.context(roots={'other': '/tmp/other-root'}),
            'other:tools/patcher.py',
        )

        self.assertIsNone(error)
        self.assertEqual(root, '/tmp/other-root')
        self.assertEqual(relative, 'tools/patcher.py')

    def test_unknown_root_is_refused(self):
        root, relative, error = resolve_root(
            self.context(roots={'other': '/tmp/other-root'}),
            'missing:tools/patcher.py',
        )

        self.assertIsNotNone(error)
        self.assertIn('missing', error)
        self.assertIsNone(root)

    def test_unknown_root_names_the_known_roots(self):
        """The error must tell Jack what is actually available."""
        _, _, error = resolve_root(
            self.context(roots={'other': '/tmp/other-root'}),
            'typo:file.txt',
        )

        self.assertIn('other', error)


class SafeTargetHonoursRoots(ForgeCase):

    def context(self, roots=None):
        environment = {
            'project_root': self.project_root,
            'forge_home': self.forge_home,
        }

        if roots is not None:
            environment['roots'] = roots

        return {'environment': environment}

    def test_default_resolution_is_unchanged(self):
        root, abs_path, error = safe_target(self.context(), 'app.py')

        self.assertIsNone(error)
        self.assertEqual(root, self.project_root)
        self.assertTrue(abs_path.endswith('app.py'))
        self.assertTrue(abs_path.startswith(self.project_root))

    def test_escape_is_still_refused(self):
        """Root support must not weaken the existing containment check."""
        _, _, error = safe_target(self.context(), '../outside.txt')

        self.assertIsNotNone(error)

    def test_escape_is_refused_inside_a_named_root(self):
        root, _, error = safe_target(
            self.context(roots={'other': '/tmp/other-root'}),
            'other:../outside.txt',
        )

        self.assertIsNotNone(error)

    def test_unknown_root_returns_an_error_not_a_path(self):
        root, abs_path, error = safe_target(
            self.context(), 'nowhere:file.txt',
        )

        self.assertIsNotNone(error)
        self.assertIsNone(abs_path)


if __name__ == '__main__':
    unittest.main()