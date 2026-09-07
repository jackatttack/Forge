# -*- coding: utf-8 -*-
"""Exercise documentation through the intended Forge runtime.

Run with the checkout isolation runner when invoked from an installed host.
Also usable by the repository's installed-wheel test mode.
"""

import re
import unittest

from forge_case import ForgeCase, bundle
from forge_under_test import forge_under_test

forge = forge_under_test()

from forge import docs
from forge.standard import first_boot_text


class DocumentationResources(unittest.TestCase):

    def test_every_catalogue_guide_loads(self):
        entries = docs.catalogue()
        identifiers = [entry['id'] for entry in entries]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for entry in entries:
            text = docs.read_guide(entry['id'])
            self.assertTrue(text.strip(), entry)
            self.assertIn('Next commands:', text)

    def test_guide_links_resolve_including_boot(self):
        texts = [first_boot_text()]
        texts.extend(docs.read_guide(item['id']) for item in docs.catalogue())
        for text in texts:
            for name in re.findall(r'FORGE docs ([a-z][a-z-]*)', text):
                self.assertTrue(docs.read_guide(name), name)

    def test_paths_cannot_select_arbitrary_resources(self):
        for name in ('../FIRST_BOOT', '/etc/passwd', 'inspect.txt', 'missing'):
            with self.assertRaises(KeyError):
                docs.read_guide(name)

    def test_exact_names_rank_first(self):
        for item in docs.catalogue():
            self.assertEqual(docs.search(item['id'])[0]['id'], item['id'])

    def test_task_queries_find_useful_guides(self):
        cases = (
            ('undo rollback restore', 'recover'),
            ('naming comments docstrings', 'human-owned-code'),
            ('clipboard checkout installed', 'workflow'),
            ('replace insert mutation', 'edit'),
            ('locate directory structure', 'inspect'),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(docs.search(query)[0]['id'], expected)

    def test_search_keeps_code_and_is_bounded_and_repeatable(self):
        hits = docs.search('`REPLACE`')
        self.assertIn('edit', [hit['id'] for hit in hits])
        query = 'inspect edit recover workflow code'
        self.assertLessEqual(len(docs.search(query)), 3)
        self.assertEqual(docs.search(query), docs.search(query))
        self.assertEqual(docs.search('zzzzunfindablezzzz'), [])

    def test_invalid_search_queries(self):
        for query in ('', '   ', 'x' * 241):
            with self.assertRaises(ValueError):
                docs.search(query)


class DocumentationCommands(ForgeCase):

    def result_for(self, command, status='APPLIED'):
        run = self.run_bundle(bundle(command))
        self.assertEqual(self.statuses(run), [status], run)
        return run['results'][0]

    def test_catalogue_and_guide(self):
        index = self.result_for('FORGE docs')
        self.assertIn('FORGE docs inspect', index['preview'])
        guide = self.result_for('FORGE docs edit')
        self.assertEqual(guide['preview'], docs.read_guide('edit').rstrip())

    def test_search_and_no_results(self):
        result = self.result_for('FORGE search docs undo rollback')
        self.assertEqual(result['data']['guides'][0]['id'], 'recover')
        self.assertIn('FORGE docs recover', result['preview'])
        empty = self.result_for('FORGE search docs zzzzunfindablezzzz')
        self.assertEqual(empty['data']['guides'], [])
        self.assertIn('FORGE docs', empty['preview'])

    def test_invalid_commands_are_explicit(self):
        self.result_for('FORGE docs missing', 'FAILED_NOT_FOUND')
        self.result_for('FORGE docs ../FIRST_BOOT', 'FAILED_NOT_FOUND')
        self.result_for('FORGE docs edit extra', 'FAILED_PARSE')
        self.result_for('FORGE search docs', 'FAILED_PARSE')
        self.result_for('FORGE search elsewhere', 'FAILED_PARSE')

    def test_boot_and_help_expose_documentation(self):
        boot = self.result_for('FORGE boot')['preview']
        self.assertIn('FORGE search docs <query>', boot)
        home = self.result_for('FORGE')['preview']
        self.assertIn('FORGE docs <name>', home)
        help_text = self.result_for('FORGE help FORGE full')['preview']
        self.assertIn('FORGE search docs undo a change', help_text)

    def test_package_audit(self):
        self.result_for('FORGE audit')


if __name__ == '__main__':
    unittest.main()