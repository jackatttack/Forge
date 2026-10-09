# -*- coding: utf-8 -*-
"""The trusted personal-ops folder: default, configured, and safe fallback."""

import os
import shutil
import tempfile
import unittest

from forge.core.config import resolve_config
from forge.core.environment import make_environment


class OpsRoot(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, 'home')
        self.project = os.path.join(self.tmp, 'project')
        os.makedirs(self.home)
        os.makedirs(self.project)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_default_is_forge_home_ops(self):
        env = make_environment(self.project, self.home)
        self.assertEqual(env['ops_root'], os.path.join(os.path.abspath(self.home), 'ops'))
        self.assertEqual(env['ops_root_warning'], '')

    def test_configured_folder_is_used(self):
        ops = os.path.join(self.project, 'forge_local', 'ops')
        os.makedirs(ops)
        env = make_environment(self.project, self.home, ops_root=ops)
        self.assertEqual(env['ops_root'], os.path.abspath(ops))
        self.assertEqual(env['ops_root_warning'], '')

    def test_missing_folder_falls_back_with_warning(self):
        missing = os.path.join(self.tmp, 'missing')
        env = make_environment(self.project, self.home, ops_root=missing)
        self.assertEqual(env['ops_root'], os.path.join(os.path.abspath(self.home), 'ops'))
        self.assertIn('not found', env['ops_root_warning'])

    def test_config_default_resolves_to_forge_home_ops(self):
        resolved = resolve_config({}, self.home)
        self.assertEqual(resolved['ops_root'], os.path.join(os.path.abspath(self.home), 'ops'))

    def test_config_relative_path_resolves_against_forge_home(self):
        config = {'paths': {'ops_root': '../project/forge_local/ops'}}
        resolved = resolve_config(config, self.home)
        self.assertEqual(
            resolved['ops_root'],
            os.path.abspath(os.path.join(self.project, 'forge_local', 'ops')),
        )


if __name__ == '__main__':
    unittest.main()