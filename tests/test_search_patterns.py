# -*- coding: utf-8 -*-
"""
SEARCH body patterns (several at once, per-pattern LIMIT) and GLOB scoping.
"""

import unittest

from forge_case import ForgeCase, bundle


def first_result(run):
    return (run.get('results') or [])[0]


def pattern_counts(run):
    patterns = (first_result(run).get('data') or {}).get('patterns') or []
    return dict((item['pattern'], item['hits']) for item in patterns)


def hit_files(run):
    hits = (first_result(run).get('data') or {}).get('hits') or []
    return sorted(set(hit['file'] for hit in hits))


class SearchPatterns(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('a_family.py', "difficulty_descriptions = 1\nGeneratorInfo(id='a')\n")
        self.put('b_family.py', "GeneratorInfo(id='b')\n")
        self.put('notes.txt', 'difficulty_descriptions in notes\n')
        self.put('noisy.py', 'noise\n' * 30)

    def search(self, *lines):
        return self.run_bundle(bundle(*lines))

    def search_patterns(self, patterns, *directives):
        return self.search(
            'SEARCH .',
            *(list(directives) + ['BEGIN_BODY'] + list(patterns) + ['END_BODY'])
        )

    def test_patterns_are_counted_and_grouped_separately(self):
        run = self.search_patterns(['difficulty_descriptions', 'GeneratorInfo'])
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(
            pattern_counts(run),
            {'difficulty_descriptions': 2, 'GeneratorInfo': 2},
        )
        preview = first_result(run).get('preview') or ''
        self.assertIn('Patterns:', preview)
        self.assertIn("--- 'GeneratorInfo': 2 hits ---", preview)

    def test_limit_applies_to_each_pattern(self):
        run = self.search_patterns(['noise', 'GeneratorInfo'], 'LIMIT: 5')
        self.assertEqual(pattern_counts(run), {'noise': 5, 'GeneratorInfo': 2})
        result = first_result(run)
        self.assertIn('LIMIT reached', result.get('preview') or '')
        self.assertIn('LIMIT reached for 1', result.get('message') or '')

    def test_regex_patterns(self):
        run = self.search_patterns(['^Gen', "id='b'"], 'MATCH: regex')
        self.assertEqual(pattern_counts(run), {'^Gen': 2, "id='b'": 1})

    def test_expect_hits_judges_the_total(self):
        run = self.search_patterns(
            ['difficulty_descriptions', 'GeneratorInfo'],
            'EXPECT_HITS: 4',
        )
        self.assertEqual(self.statuses(run), ['APPLIED'])

    def test_single_pattern_search_is_unchanged(self):
        run = self.search('SEARCH . FOR GeneratorInfo')
        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertNotIn('Patterns:', first_result(run).get('preview') or '')

    def test_glob_scopes_a_single_pattern_search(self):
        run = self.search(
            'SEARCH . FOR difficulty_descriptions',
            'GLOB: *_family.py',
        )
        self.assertEqual(hit_files(run), ['a_family.py'])

    def test_glob_scopes_body_patterns(self):
        run = self.search_patterns(
            ['difficulty_descriptions', 'noise'],
            'GLOB: *_FAMILY.py',
        )
        self.assertEqual(pattern_counts(run), {'difficulty_descriptions': 1, 'noise': 0})

    def test_glob_with_a_path_is_refused(self):
        run = self.search('SEARCH . FOR noise', 'GLOB: sub/*.py')
        self.assertNotIn('APPLIED', self.statuses(run))

    def test_body_patterns_and_inline_query_are_refused(self):
        run = self.search(
            'SEARCH . FOR noise',
            'BEGIN_BODY',
            'GeneratorInfo',
            'END_BODY',
        )
        self.assertNotIn('APPLIED', self.statuses(run))

    def test_body_patterns_with_ast_are_refused(self):
        run = self.search_patterns(['GeneratorInfo'], 'MATCH: ast')
        self.assertNotIn('APPLIED', self.statuses(run))

    def test_invalid_regex_pattern_is_refused(self):
        run = self.search_patterns(['ok', '(unclosed'], 'MATCH: regex')
        self.assertNotIn('APPLIED', self.statuses(run))


if __name__ == '__main__':
    unittest.main()