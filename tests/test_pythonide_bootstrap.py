# -*- coding: utf-8 -*-
"""Regression tests for the PythonIDE bootstrap install boundary."""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

BOOTSTRAP_PATH = os.path.join(
    ROOT,
    'bootstrap',
    'pythonide.py',
)


def load_bootstrap():
    spec = importlib.util.spec_from_file_location(
        'forge_pythonide_bootstrap_under_test',
        BOOTSTRAP_PATH,
    )
    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(
        module
    )
    return module


class FakeResponse(object):
    def __init__(self, payload=b''):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class PythonIDEBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.bootstrap = load_bootstrap()
        self.sha = 'b' * 40

    def test_loaded_forge_modules_reports_current_and_owned_legacy_namespaces(self):
        sentinel_names = (
            'forge',
            'forge.core',
            'forge_core',
            'forge_core.parser',
            'forge_packages',
            'forge_packages.core_ops',
            'forge_extra',
            'unrelated_module',
        )

        old = {
            name: sys.modules.get(name)
            for name in sentinel_names
        }

        try:
            for name in sentinel_names:
                sys.modules[name] = object()

            loaded = self.bootstrap.loaded_forge_modules()

            for name in (
                'forge',
                'forge.core',
                'forge_core',
                'forge_core.parser',
                'forge_packages',
                'forge_packages.core_ops',
            ):
                self.assertIn(
                    name,
                    loaded,
                )

            self.assertNotIn(
                'forge_extra',
                loaded,
            )
            self.assertNotIn(
                'unrelated_module',
                loaded,
            )

        finally:
            for name, value in old.items():
                if value is None:
                    sys.modules.pop(
                        name,
                        None,
                    )
                else:
                    sys.modules[name] = value

    def test_revision_marker_records_exact_commit_in_workspace_runtime(self):
        with tempfile.TemporaryDirectory() as workspace:
            package_root = os.path.join(
                workspace,
                'forge',
            )
            os.makedirs(
                package_root
            )

            path = self.bootstrap.write_revision_marker(
                workspace,
                self.sha,
            )

            self.assertEqual(
                path,
                os.path.join(
                    workspace,
                    'forge',
                    self.bootstrap.REVISION_MARKER_NAME,
                ),
            )

            with open(
                path,
                'r',
                encoding='utf-8',
            ) as handle:
                self.assertEqual(
                    handle.read(),
                    self.sha + '\n',
                )

    def test_main_uses_one_resolved_commit_for_installer_and_archive(self):
        seen = {
            'urls': [],
            'argv': None,
            'marker': None,
        }

        def fake_urlopen(url):
            seen['urls'].append(
                str(url)
            )
            return FakeResponse(
                b'# installer placeholder\n'
            )

        def fake_run_path(_path, run_name=None):
            self.assertEqual(
                run_name,
                '__main__',
            )
            seen['argv'] = list(
                sys.argv
            )

        def fake_marker(workspace, commit):
            seen['marker'] = (
                workspace,
                commit,
            )
            return os.path.join(
                workspace,
                'forge',
                '.portable-forge-revision',
            )

        with tempfile.TemporaryDirectory() as workspace:
            old_cwd = os.getcwd()

            try:
                os.chdir(
                    workspace
                )

                with mock.patch.object(
                    self.bootstrap,
                    'resolve_ref',
                    return_value=self.sha,
                ), mock.patch.object(
                    self.bootstrap,
                    'loaded_forge_modules',
                    return_value=[],
                ), mock.patch.object(
                    self.bootstrap.urllib.request,
                    'urlopen',
                    side_effect=fake_urlopen,
                ), mock.patch.object(
                    self.bootstrap.runpy,
                    'run_path',
                    side_effect=fake_run_path,
                ), mock.patch.object(
                    self.bootstrap,
                    'write_revision_marker',
                    side_effect=fake_marker,
                ):
                    self.bootstrap.main()

            finally:
                os.chdir(
                    old_cwd
                )

        self.assertEqual(
            len(seen['urls']),
            1,
        )
        self.assertIn(
            '/' + self.sha + '/install.py',
            seen['urls'][0],
        )

        marker_workspace, marker_commit = seen['marker']

        self.assertEqual(
            marker_commit,
            self.sha,
        )
        self.assertEqual(
            marker_workspace,
            os.path.abspath(workspace),
        )

        argv = seen['argv']
        self.assertIsNotNone(
            argv
        )

        ref_index = argv.index(
            '--ref'
        )
        self.assertEqual(
            argv[ref_index + 1],
            self.sha,
        )

        workspace_index = argv.index(
            '--pythonide-workspace'
        )
        self.assertEqual(
            argv[workspace_index + 1],
            os.path.abspath(workspace),
        )

    def test_main_warns_when_forge_is_already_loaded(self):
        output = io.StringIO()

        with tempfile.TemporaryDirectory() as workspace:
            old_cwd = os.getcwd()

            try:
                os.chdir(
                    workspace
                )

                with mock.patch.object(
                    self.bootstrap,
                    'resolve_ref',
                    return_value=self.sha,
                ), mock.patch.object(
                    self.bootstrap,
                    'loaded_forge_modules',
                    return_value=[
                        'forge',
                        'forge_core',
                        'forge_packages',
                    ],
                ), mock.patch.object(
                    self.bootstrap.urllib.request,
                    'urlopen',
                    return_value=FakeResponse(
                        b'# installer placeholder\n'
                    ),
                ), mock.patch.object(
                    self.bootstrap.runpy,
                    'run_path',
                    return_value={},
                ), mock.patch.object(
                    self.bootstrap,
                    'write_revision_marker',
                    return_value=os.path.join(
                        workspace,
                        'forge',
                        '.portable-forge-revision',
                    ),
                ), contextlib.redirect_stdout(
                    output
                ):
                    self.bootstrap.main()

            finally:
                os.chdir(
                    old_cwd
                )

        text = output.getvalue()

        self.assertIn(
            'WARNING:',
            text,
        )
        self.assertIn(
            'Restart the Python interpreter before running Forge again.',
            text,
        )
        self.assertIn(
            'Loaded Forge modules: 3',
            text,
        )
        self.assertIn(
            'Active runtime: unchanged until restart',
            text,
        )


if __name__ == '__main__':
    unittest.main()
