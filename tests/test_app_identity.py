# -*- coding: utf-8 -*-
"""detect_app() names the app from sys.executable."""

import importlib
import sys
import unittest

import forge_case  # noqa: F401  loads the checkout Forge first

app_identity = importlib.import_module('forge.core.app_identity')


class DetectApp(unittest.TestCase):

    def setUp(self):
        self._executable = sys.executable

    def tearDown(self):
        sys.executable = self._executable

    def check(self, executable, expected):
        sys.executable = executable
        self.assertEqual(app_identity.detect_app(), expected)

    def test_pythonista(self):
        self.check('/private/var/containers/Bundle/Application/A/'
                   'Pythonista3.app/Pythonista3', 'pythonista')

    def test_pythonide(self):
        self.check('/private/var/containers/Bundle/Application/B/'
                   'Python IDE.app/Python IDE', 'pythonide')

    def test_juno(self):
        self.check('/private/var/containers/Bundle/Application/C/'
                   'Juno.app/Juno', 'juno')

    def test_anything_else_is_unknown(self):
        self.check('/usr/bin/python3', 'unknown')


if __name__ == '__main__':
    unittest.main()