# -*- coding: utf-8 -*-
"""
A repeated OLD block names where it matched, so the fix needs no READ.

Covers near_match.describe_matches and its use by REPLACE (DELETE shares
the same call). Feedback 2026-11-23: "self.tier = None" also matched inside
"self.tier = None if value == self.tier else value".
"""

import unittest

from forge.core.near_match import describe_matches
from forge_case import ForgeCase, bundle


class DescribeMatches(unittest.TestCase):

    def test_lists_each_match_with_its_line_number(self):
        text = 'a = 1\nx = None\nb = 2\nx = None\n'
        described = describe_matches(text, 'x = None')
        self.assertIn('1. line 2:', described)
        self.assertIn('2. line 4:', described)
        self.assertNotIn('inside a longer line', described)

    def test_flags_a_match_inside_a_longer_line(self):
        text = '    self.tier = None\n    self.tier = None if value else value\n'
        described = describe_matches(text, '    self.tier = None')
        lines = described.splitlines()
        self.assertNotIn('inside a longer line', lines[1])
        self.assertIn('2. line 2:', lines[2])
        self.assertIn('(inside a longer line)', lines[2])
        self.assertIn('widen it to whole lines', described)

    def test_long_lists_are_capped(self):
        described = describe_matches('k\n' * 20, 'k')
        self.assertIn('(+12 more)', described)


class AmbiguousReplaceNamesMatches(ForgeCase):

    def test_failure_lists_the_matches(self):
        self.put('app.py', 'x = None\ny = 1\nx = None if y else 2\n')
        run = self.run_bundle(bundle(
            'REPLACE app.py',
            'BEGIN_OLD',
            'x = None',
            'END_OLD',
            'BEGIN_NEW',
            'x = 0',
            'END_NEW',
        ))
        result = (run.get('results') or [])[0]
        self.assertEqual(result.get('status'), 'FAILED_AMBIGUOUS')
        message = str(result.get('message') or '')
        self.assertIn('1. line 1:', message)
        self.assertIn('2. line 3:', message)
        self.assertIn('(inside a longer line)', message)


if __name__ == '__main__':
    unittest.main()