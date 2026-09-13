# -*- coding: utf-8 -*-
"""
Configured named roots must survive validation and resolution intact.

A root name becomes a path prefix, so a malformed name has to fail at
configuration time with a clear message. A silently accepted bad root
would surface much later as a confusing unknown-root error, or worse,
as a path resolved against the wrong tree.
"""

import os
import unittest

from forge.core.config import (
    default_config,
    normalise_config,
    resolve_config,
)


FORGE_HOME = os.path.join(os.sep, 'tmp', 'forge-home')


class RootsDefault(unittest.TestCase):

    def test_default_config_has_an_empty_roots_map(self):
        """No configuration means no extra roots, not a missing key."""
        self.assertEqual(default_config()['roots'], {})

    def test_config_without_roots_still_normalises(self):
        """Existing configs predate this setting and must keep working."""
        merged = normalise_config({'config_version': 1})

        self.assertEqual(merged['roots'], {})


class RootsValidation(unittest.TestCase):

    def normalise(self, roots):
        return normalise_config({'config_version': 1, 'roots': roots})

    def test_a_named_root_is_accepted(self):
        merged = self.normalise({'icloud': '/some/where'})

        self.assertEqual(merged['roots']['icloud'], '/some/where')

    def test_roots_must_be_an_object(self):
        with self.assertRaises(ValueError):
            self.normalise(['icloud'])

    def test_root_path_must_be_a_string(self):
        with self.assertRaises(ValueError):
            self.normalise({'icloud': 42})

    def test_root_path_cannot_be_empty(self):
        with self.assertRaises(ValueError):
            self.normalise({'icloud': '   '})

    def test_root_name_cannot_contain_a_colon(self):
        """The name is used as a "name:path" prefix, so a colon breaks it."""
        with self.assertRaises(ValueError):
            self.normalise({'ic:loud': '/some/where'})

    def test_root_name_cannot_contain_a_separator(self):
        with self.assertRaises(ValueError):
            self.normalise({'ic/loud': '/some/where'})

    def test_root_name_cannot_be_empty(self):
        with self.assertRaises(ValueError):
            self.normalise({'   ': '/some/where'})


class RootsResolution(unittest.TestCase):

    def resolve(self, roots):
        return resolve_config(
            {'config_version': 1, 'roots': roots},
            FORGE_HOME,
        )

    def test_absolute_root_is_kept(self):
        resolved = self.resolve({'icloud': '/absolute/target'})

        self.assertEqual(
            resolved['roots']['icloud'],
            os.path.abspath('/absolute/target'),
        )

    def test_relative_root_resolves_against_forge_home(self):
        resolved = self.resolve({'nearby': 'sibling'})

        self.assertEqual(
            resolved['roots']['nearby'],
            os.path.join(FORGE_HOME, 'sibling'),
        )

    def test_no_roots_resolves_to_an_empty_map(self):
        resolved = resolve_config({'config_version': 1}, FORGE_HOME)

        self.assertEqual(resolved['roots'], {})

    def test_several_roots_are_all_resolved(self):
        resolved = self.resolve({
            'icloud': '/one/place',
            'other': '/another/place',
        })

        self.assertEqual(len(resolved['roots']), 2)
        self.assertIn('icloud', resolved['roots'])
        self.assertIn('other', resolved['roots'])


if __name__ == '__main__':
    unittest.main()