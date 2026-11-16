# -*- coding: utf-8 -*-
"""
Headless tests for the presenter's automatic choice.

With no presenter in forge.json, Forge uses the Anvil run view it ships
with when editorkit and its Toolbox are installed, and the built-in landing
otherwise. "builtin" keeps the built-in landing; a named presenter wins.
"""

import tempfile
import types
import unittest

from forge.adapters.pythonista import presenter


BOTH = ('editorkit', 'editorkit_toolbox')


def finder_for(installed):
    """A find_spec stand-in: found for the names in installed only."""
    def finder(name):
        return object() if name in installed else None
    return finder


class Importer(object):
    """Records the names asked for and returns a working presenter."""

    def __init__(self):
        self.names = []
        self.module = types.ModuleType('fake_presenter')
        self.module.show_after_run = lambda run, progress=None: True

    def __call__(self, name):
        self.names.append(name)
        return self.module


class AutomaticChoice(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = self.temp.name           # no forge.json: no presenter set

    def tearDown(self):
        self.temp.cleanup()

    def test_editorkit_and_toolbox_installed_means_anvil(self):
        importer = Importer()
        module = presenter.load(forge_home=self.home, importer=importer,
                                finder=finder_for(BOTH))
        self.assertIs(module, importer.module)
        self.assertEqual(importer.names, [presenter.BUNDLED])

    def test_without_the_toolbox_the_builtin_landing_stays(self):
        importer = Importer()
        module = presenter.load(forge_home=self.home, importer=importer,
                                finder=finder_for(('editorkit',)))
        self.assertIsNone(module)
        self.assertEqual(importer.names, [])

    def test_builtin_keeps_the_builtin_landing(self):
        importer = Importer()
        module = presenter.load(name=presenter.BUILTIN, importer=importer,
                                finder=finder_for(BOTH))
        self.assertIsNone(module)
        self.assertEqual(importer.names, [])

    def test_a_named_presenter_wins(self):
        importer = Importer()
        presenter.load(name='my_package.forge_presenter', importer=importer,
                       finder=finder_for(BOTH))
        self.assertEqual(importer.names, ['my_package.forge_presenter'])

    def test_a_finder_error_means_the_builtin_landing(self):
        def broken(name):
            raise ValueError(name)
        self.assertEqual(presenter.bundled_name(broken), '')

    def test_make_listener_passes_the_finder_through(self):
        importer = Importer()
        presenter.make_listener(lambda live=True: object(), forge_home=self.home,
                                importer=importer, finder=finder_for(BOTH))
        self.assertEqual(importer.names, [presenter.BUNDLED])


if __name__ == '__main__':
    unittest.main()