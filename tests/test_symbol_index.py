# -*- coding: utf-8 -*-
"""
Symbol index used by MAP MODE: symbols.
"""

import os
import shutil
import tempfile
import unittest

import forge_case  # noqa: F401  (puts the checkout Forge on sys.path)
from forge.core.symbol_index import (
    collect_python_files,
    render_symbol_index,
    summarise_file,
)


SKIP = set(['__pycache__'])

FAMILY_SOURCE = (
    'from .core import GeneratorInfo\n'
    '\n'
    "INFO = GeneratorInfo(id='bounds', title='Bounds')\n"
    '\n'
    'class BoundsGenerator:\n'
    '    def inner(self):\n'
    '        pass\n'
    '\n'
    'def make():\n'
    "    info = GeneratorInfo(id='bounds_lower')\n"
    '    return info\n'
    '\n'
    'async def later():\n'
    '    pass\n'
    '\n'
    "id = 'bounds'\n"
    'id = make()\n'
)


class SymbolIndexCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='forge-symbols-')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def put(self, relative_path, text):
        path = os.path.join(self.root, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path


class SummariseFile(SymbolIndexCase):

    def test_lists_top_level_classes_and_functions_in_order(self):
        summary = summarise_file(self.put('pkg/bounds_family.py', FAMILY_SOURCE))
        self.assertEqual(summary['classes'], ['BoundsGenerator'])
        self.assertEqual(summary['functions'], ['make', 'later'])
        self.assertEqual(summary['error'], '')

    def test_key_values_cover_keywords_and_assignments_in_source_order(self):
        summary = summarise_file(self.put('pkg/bounds_family.py', FAMILY_SOURCE), key='id')
        self.assertEqual(summary['key_values'], ["'bounds'", "'bounds_lower'", '<expr>'])

    def test_syntax_error_is_reported_not_dropped(self):
        summary = summarise_file(self.put('pkg/broken.py', 'def oops(:\n'))
        self.assertTrue(summary['error'].startswith('syntax error line 1'))


class CollectFiles(SymbolIndexCase):

    def test_prunes_skipped_and_dot_dirs_and_counts_other_files(self):
        self.put('pkg/a.py', '')
        self.put('pkg/__pycache__/a.py', '')
        self.put('pkg/.hidden/b.py', '')
        self.put('pkg/notes.txt', '')
        paths, stats = collect_python_files(self.root, SKIP)
        self.assertEqual([os.path.basename(p) for p in paths], ['a.py'])
        self.assertEqual(stats['skipped_dirs'], ['.hidden', '__pycache__'])
        self.assertEqual(stats['non_python'], 1)

    def test_glob_keeps_matching_names_and_counts_the_rest(self):
        self.put('pkg/a_family.py', '')
        self.put('pkg/b_family.py', '')
        self.put('pkg/core.py', '')
        paths, stats = collect_python_files(self.root, SKIP, ['*_FAMILY.py'])
        self.assertEqual(len(paths), 2)
        self.assertEqual(stats['skipped_by_glob'], 1)


class RenderIndex(SymbolIndexCase):

    def test_one_line_per_file_with_key(self):
        self.put('pkg/bounds_family.py', FAMILY_SOURCE)
        text = '\n'.join(render_symbol_index(self.root, 'proj', SKIP, key='id'))
        # Index lines wrap, so compare with the wrapping undone.
        unwrapped = ' '.join(text.split())
        self.assertIn('TYPE=symbol-index', text)
        self.assertIn('key: id', text)
        self.assertIn('pkg/bounds_family.py — classes: BoundsGenerator', unwrapped)
        self.assertIn("id: 'bounds', 'bounds_lower', <expr>", unwrapped)

    def test_limit_counts_the_files_left_out(self):
        for n in range(5):
            self.put('pkg/m%d.py' % n, 'def f():\n    pass\n')
        text = '\n'.join(render_symbol_index(self.root, 'proj', SKIP, limit=2))
        self.assertIn('3 more files not shown (LIMIT 2)', text)
        self.assertNotIn('m4.py', text)

    def test_empty_tree_says_so(self):
        text = '\n'.join(render_symbol_index(self.root, 'proj', SKIP))
        self.assertIn('(no Python files)', text)


class MapSymbolsMode(forge_case.ForgeCase):
    """MAP MODE: symbols, GLOB and KEY, run through real bundles."""

    def map_preview(self, *lines):
        run = self.run_bundle(forge_case.bundle(*lines))
        return self.statuses(run), str((run.get('results') or [{}])[0].get('preview') or '')

    def test_symbols_mode_renders_the_index(self):
        self.put('a_family.py', FAMILY_SOURCE)
        statuses, preview = self.map_preview('MAP .', 'MODE: symbols', 'KEY: id')
        self.assertEqual(statuses, ['APPLIED'])
        self.assertIn('TYPE=symbol-index', preview)
        self.assertIn('a_family.py — classes: BoundsGenerator', preview)

    def test_glob_outside_symbols_mode_is_refused(self):
        statuses, _ = self.map_preview('MAP .', 'GLOB: *.py')
        self.assertNotIn('APPLIED', statuses)

    def test_key_must_be_a_python_name(self):
        statuses, _ = self.map_preview('MAP .', 'MODE: symbols', 'KEY: 1bad')
        self.assertNotIn('APPLIED', statuses)

    def test_truncated_directory_map_points_at_symbols(self):
        for n in range(5):
            self.put('m%d.py' % n, '')
        _, preview = self.map_preview('MAP .', 'LIMIT: 2')
        self.assertIn('MODE: symbols', preview)

    def test_complete_directory_map_has_no_pointer(self):
        self.put('m0.py', '')
        _, preview = self.map_preview('MAP .')
        self.assertNotIn('MODE: symbols', preview)


if __name__ == '__main__':
    unittest.main()