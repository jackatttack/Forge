# -*- coding: utf-8 -*-
"""Shared TestCase base for Forge behaviour tests."""

import os
import sys
import tempfile
import unittest

sys.path.insert(
    0,
    os.path.dirname(os.path.abspath(__file__)),
)

from forge_under_test import (
    describe_forge_under_test,
    forge_under_test,
)


forge = forge_under_test()

print(describe_forge_under_test(forge))


def bundle(*lines):
    """
    Build bundle text from separate lines.

    Bundle body markers must never appear at column 0 inside a Python
    string literal in this repository, because these test files are
    themselves edited through Forge bundles.
    """
    return '\n'.join(lines)


class ForgeCase(unittest.TestCase):
    """A test case with a disposable project root and a bundle runner."""

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix='forge-test-')
        self.forge_home = os.path.join(self.project_root, '.forge')

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

    def put(self, relative_path, text):
        path = os.path.join(self.project_root, relative_path)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def get(self, relative_path):
        path = os.path.join(self.project_root, relative_path)
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()

    def exists(self, relative_path):
        return os.path.exists(
            os.path.join(self.project_root, relative_path)
        )