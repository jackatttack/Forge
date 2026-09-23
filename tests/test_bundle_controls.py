# -*- coding: utf-8 -*-
"""
Opt-in bundle controls: a bundle can ask to stop itself.
"""

import unittest

from forge_case import ForgeCase, bundle
from forge.core.bundle_controls import count_meets, parse_count_expectation


class StopOnFail(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('fail.py', 'raise SystemExit(1)\n')
        self.put('ok.py', 'print("ok")\n')

    def gated_write_after(self, script):
        return self.run_bundle(bundle(
            'RUN ' + script,
            'STOP_ON_FAIL: yes',
            '',
            'WRITE after.txt',
            'BEGIN_BODY',
            'written',
            'END_BODY',
            '',
            'READ fail.py',
        ))

    def test_failed_gated_run_stops_later_mutations(self):
        run = self.gated_write_after('fail.py')
        statuses = self.statuses(run)
        self.assertNotEqual(statuses[0], 'APPLIED')
        self.assertEqual(statuses[1], 'SKIPPED_AFTER_FAILURE')
        self.assertFalse(self.exists('after.txt'))

    def test_reads_still_run_after_a_gate_stops(self):
        run = self.gated_write_after('fail.py')
        self.assertEqual(self.statuses(run)[2], 'APPLIED')

    def test_passing_gated_run_lets_the_bundle_continue(self):
        run = self.gated_write_after('ok.py')
        self.assertEqual(self.statuses(run), ['APPLIED', 'APPLIED', 'APPLIED'])
        self.assertTrue(self.exists('after.txt'))

    def test_ungated_failed_run_is_still_only_an_observation(self):
        run = self.run_bundle(bundle(
            'RUN fail.py',
            '',
            'WRITE after.txt',
            'BEGIN_BODY',
            'written',
            'END_BODY',
        ))
        self.assertEqual(self.statuses(run)[1], 'APPLIED')


class CountExpectations(unittest.TestCase):

    def test_plain_number_means_exactly(self):
        self.assertEqual(parse_count_expectation('0'), ('=', 0))
        self.assertTrue(count_meets(0, ('=', 0)))
        self.assertFalse(count_meets(1, ('=', 0)))

    def test_comparisons(self):
        self.assertTrue(count_meets(3, parse_count_expectation('>0')))
        self.assertTrue(count_meets(2, parse_count_expectation('>=2')))
        self.assertTrue(count_meets(4, parse_count_expectation('<5')))
        self.assertFalse(count_meets(6, parse_count_expectation('<=5')))

    def test_nonsense_is_a_readable_error(self):
        with self.assertRaises(ValueError):
            parse_count_expectation('lots')


class ExpectHits(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('app.py', 'old_name = 1\nprint(old_name)\n')

    def search(self, *directives):
        return self.run_bundle(bundle('SEARCH app.py FOR old_name', *directives))

    def test_met_expectation_applies(self):
        self.assertEqual(self.statuses(self.search('EXPECT_HITS: 2')), ['APPLIED'])

    def test_comparison_expectation_applies(self):
        self.assertEqual(self.statuses(self.search('EXPECT_HITS: >0')), ['APPLIED'])

    def test_unmet_expectation_fails_and_stops_mutations(self):
        run = self.run_bundle(bundle(
            'SEARCH app.py FOR old_name',
            'EXPECT_HITS: 0',
            '',
            'WRITE after.txt',
            'BEGIN_BODY',
            'written',
            'END_BODY',
        ))
        self.assertEqual(
            self.statuses(run),
            ['FAILED_EXPECTATION', 'SKIPPED_AFTER_FAILURE'],
        )
        self.assertFalse(self.exists('after.txt'))

    def test_nonsense_expectation_fails(self):
        self.assertEqual(
            self.statuses(self.search('EXPECT_HITS: lots')),
            ['FAILED_EXPECTATION'],
        )

    def test_exact_count_beyond_limit_is_not_guessed(self):
        run = self.search('LIMIT: 1', 'EXPECT_HITS: 1')
        self.assertEqual(self.statuses(run), ['FAILED_EXPECTATION'])


if __name__ == '__main__':
    unittest.main()