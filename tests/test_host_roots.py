# -*- coding: utf-8 -*-
"""
The opt-in host_roots feature adds forge_home: and home: roots.

These tests run real bundles against a written forge.json, like
test_root_end_to_end, so they prove the whole chain from configuration to
path resolution. Off by default; configured roots of the same name win.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from forge_case import bundle

import forge
from forge.core.config import resolve_config


class HostRootsCase(unittest.TestCase):
    """A project root, a forge home, a fake user home and a written forge.json."""

    def setUp(self):
        self.temporary = tempfile.mkdtemp(prefix='forge-host-roots-')
        self.addCleanup(shutil.rmtree, self.temporary, True)

        self.project_root = os.path.join(self.temporary, 'project')
        self.forge_home = os.path.join(self.temporary, '.forge')
        self.user_home = os.path.join(self.temporary, 'user_home')
        self.other_root = os.path.join(self.temporary, 'elsewhere')

        for folder in (self.project_root, self.forge_home,
                       self.user_home, self.other_root):
            os.makedirs(folder)

        # expanduser('~') reads HOME, so point it at the fake user home.
        patcher = mock.patch.dict(os.environ, {'HOME': self.user_home})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_config(self, payload):
        payload = dict({'config_version': 1}, **payload)
        with open(os.path.join(self.forge_home, 'forge.json'), 'w',
                  encoding='utf-8') as handle:
            json.dump(payload, handle)

    def put(self, root, relative_path, text):
        with open(os.path.join(root, relative_path), 'w',
                  encoding='utf-8') as handle:
            handle.write(text)

    def first_status(self, text):
        run = forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='test',
            store=False,
        )
        return str(run['results'][0].get('status') or '')


class HostRootsAreOptIn(HostRootsCase):

    def test_off_by_default(self):
        self.write_config({})
        self.put(self.forge_home, 'note.txt', 'x\n')
        self.assertNotEqual(self.first_status(bundle('READ forge_home:note.txt')),
                            'APPLIED')
        self.assertNotEqual(self.first_status(bundle('READ home:note.txt')),
                            'APPLIED')

    def test_explicit_false_is_off(self):
        self.write_config({'features': {'host_roots': False}})
        self.put(self.forge_home, 'note.txt', 'x\n')
        self.assertNotEqual(self.first_status(bundle('READ forge_home:note.txt')),
                            'APPLIED')


class HostRootsReachTheBundle(HostRootsCase):

    def setUp(self):
        super().setUp()
        self.write_config({'features': {'host_roots': True}})

    def test_forge_home_root_reads_forge_home(self):
        self.put(self.forge_home, 'note.txt', 'in forge home\n')
        self.assertEqual(self.first_status(bundle('READ forge_home:note.txt')),
                         'APPLIED')

    def test_home_root_reads_the_user_home(self):
        self.put(self.user_home, 'note.txt', 'in user home\n')
        self.assertEqual(self.first_status(bundle('READ home:note.txt')),
                         'APPLIED')

    def test_write_through_home_root_lands_in_the_user_home(self):
        status = self.first_status(bundle(
            'WRITE home:created.txt',
            'BEGIN_BODY',
            'hello',
            'END_BODY',
        ))
        self.assertEqual(status, 'APPLIED')
        self.assertTrue(os.path.isfile(os.path.join(self.user_home, 'created.txt')))
        self.assertFalse(os.path.exists(os.path.join(self.project_root, 'created.txt')))


class ConfiguredRootsWin(HostRootsCase):

    def test_configured_home_replaces_the_host_home(self):
        self.write_config({
            'features': {'host_roots': True},
            'roots': {'home': self.other_root},
        })
        self.put(self.other_root, 'only_here.txt', 'configured\n')
        self.assertEqual(self.first_status(bundle('READ home:only_here.txt')),
                         'APPLIED')

    def test_resolve_config_lists_both_host_roots(self):
        resolved = resolve_config(
            {'config_version': 1, 'features': {'host_roots': True}},
            self.forge_home,
        )
        self.assertEqual(resolved['roots']['forge_home'],
                         os.path.abspath(self.forge_home))
        self.assertEqual(resolved['roots']['home'],
                         os.path.abspath(self.user_home))


if __name__ == '__main__':
    unittest.main()