# -*- coding: utf-8 -*-
"""
AST targets on root-level files must not be mistaken for named roots.

"app.py::main" once parsed as root "app.py" with path ":main", so any
AST target on a file at the project root failed as an unknown root.
"""

import unittest

from forge_case import ForgeCase, bundle
from forge.core.file_safety import split_root_prefix


class DoubleColonIsNotARootPrefix(unittest.TestCase):

    def test_root_level_ast_target_has_no_prefix(self):
        self.assertEqual(split_root_prefix('app.py::main'), (None, 'app.py::main'))

    def test_named_root_with_ast_target_still_splits(self):
        self.assertEqual(
            split_root_prefix('icloud:app.py::main'),
            ('icloud', 'app.py::main'),
        )


class RootLevelAstTargetsWork(ForgeCase):

    SOURCE = 'def main():\n    return 1\n'

    def test_read_of_root_level_ast_target_applies(self):
        self.put('app.py', self.SOURCE)
        run = self.run_bundle(bundle('READ app.py::main'))
        self.assertEqual(self.statuses(run), ['APPLIED'])

    def test_replace_of_root_level_ast_target_applies(self):
        self.put('app.py', self.SOURCE)
        run = self.run_bundle(bundle(
            'REPLACE app.py::main',
            'BEGIN_BODY',
            'def main():',
            '    return 2',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertIn('return 2', self.get('app.py'))


if __name__ == '__main__':
    unittest.main()