# -*- coding: utf-8 -*-
"""
SEARCH says in its header whether case counted.

Exact, regex and AST matching ignore case unless CASE: yes, so an
EXPECT_HITS: 0 on 'LAST_EDIT' can fail on 'last_edit'. The header line
names the mode and the case rule so the packet explains itself.
"""

import unittest

from forge_case import ForgeCase, bundle


class SearchCaseHeaderTests(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('settings.py', 'LAST_EDIT = 1\nlast_edit = 2\n')

    def preview_of(self, *lines):
        run = self.run_bundle(bundle(*lines))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        return run['results'][0].get('preview') or ''

    def test_exact_default_says_any_case(self):
        preview = self.preview_of('SEARCH settings.py FOR LAST_EDIT')
        self.assertIn('MATCH=exact, any case (CASE: yes to match case)', preview)

    def test_exact_with_case_says_case_sensitive(self):
        preview = self.preview_of('SEARCH settings.py FOR LAST_EDIT', 'CASE: yes')
        self.assertIn('MATCH=exact, case-sensitive', preview)

    def test_regex_follows_case(self):
        preview = self.preview_of('SEARCH settings.py', 'QUERY: LAST_.*', 'MATCH: regex', 'CASE: yes')
        self.assertIn('MATCH=regex, case-sensitive', preview)

    def test_fuzzy_always_any_case(self):
        preview = self.preview_of('SEARCH settings.py FOR last edit', 'MATCH: fuzzy', 'CASE: yes')
        self.assertIn('MATCH=fuzzy, any case', preview)

    def test_body_patterns_header_says_case(self):
        preview = self.preview_of(
            'SEARCH .', 'BEGIN_BODY', 'LAST_EDIT', 'last_edit', 'END_BODY',
        )
        self.assertIn('MATCH=exact, any case', preview)

    def test_ast_header_says_case(self):
        preview = self.preview_of('SEARCH .', 'MATCH: ast', 'ASSIGNS: LAST_EDIT', 'CASE: yes')
        self.assertIn('MATCH=ast, case-sensitive', preview)


if __name__ == '__main__':
    unittest.main()