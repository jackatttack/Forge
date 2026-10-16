# -*- coding: utf-8 -*-
"""install.py adapter files: Juno install, refusals, and the PythonIDE wrappers."""

import importlib.util
import os
import shutil
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_installer():
    spec = importlib.util.spec_from_file_location(
        'portable_forge_install_under_test',
        os.path.join(REPO_ROOT, 'install.py'),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load_installer()


class AdapterFiles(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='forge-install-test-')
        self.documents = os.path.join(self.root, 'Documents')
        os.makedirs(self.documents)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.documents, name)

    def read(self, name):
        with open(self.path(name), encoding='utf-8') as handle:
            return handle.read()

    def write(self, name, text):
        with open(self.path(name), 'w', encoding='utf-8') as handle:
            handle.write(text)

    def test_fresh_juno_install(self):
        installed = installer.install_juno_adapter(REPO_ROOT, self.documents)

        self.assertEqual(
            sorted(os.path.basename(path) for path in installed),
            ['forge_entry.py', 'juno_clipboard.py'],
        )
        self.assertIn(installer.JUNO_LAUNCHER_MARKER, self.read('forge_entry.py'))
        self.assertIn(installer.JUNO_CLIPBOARD_MARKER,
                      self.read('juno_clipboard.py'))
        self.assertTrue(os.path.isdir(self.path(os.path.join('.forge', 'ops'))))

    def test_reinstall_unchanged_is_a_no_op(self):
        installer.install_juno_adapter(REPO_ROOT, self.documents)
        plans = installer.juno_adapter_preflight(REPO_ROOT, self.documents)

        self.assertEqual([plan['write'] for plan in plans], [False, False])

    def test_unmarked_file_is_refused_and_nothing_written(self):
        self.write('forge_entry.py', 'hand written, no marker\n')

        with self.assertRaises(RuntimeError) as caught:
            installer.install_juno_adapter(REPO_ROOT, self.documents, force=True)

        self.assertIn('unrecognised Juno adapter file', str(caught.exception))
        self.assertEqual(self.read('forge_entry.py'), 'hand written, no marker\n')
        self.assertFalse(os.path.exists(self.path('juno_clipboard.py')))

    def test_marked_but_different_needs_force(self):
        installer.install_juno_adapter(REPO_ROOT, self.documents)
        old = '# %s\nold version\n' % installer.JUNO_LAUNCHER_MARKER
        self.write('forge_entry.py', old)

        with self.assertRaises(RuntimeError):
            installer.install_juno_adapter(REPO_ROOT, self.documents)
        self.assertEqual(self.read('forge_entry.py'), old)

        installer.install_juno_adapter(REPO_ROOT, self.documents, force=True)
        self.assertNotEqual(self.read('forge_entry.py'), old)

    def test_pythonide_wrappers_still_find_their_files(self):
        plans = installer.pythonide_adapter_preflight(REPO_ROOT, self.documents)

        self.assertEqual(
            sorted(os.path.basename(plan['destination']) for plan in plans),
            sorted(name for name, _ in installer.PYTHONIDE_ADAPTER_FILES),
        )
        self.assertTrue(all(plan['created'] for plan in plans))

    def test_juno_documents_rejects_target(self):
        with self.assertRaises(RuntimeError) as caught:
            installer.main([
                '--source', REPO_ROOT,
                '--juno-documents', self.documents,
                '--target', self.root,
            ])

        self.assertIn('--juno-documents', str(caught.exception))


if __name__ == '__main__':
    unittest.main()