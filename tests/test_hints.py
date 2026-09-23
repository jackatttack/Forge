# -*- coding: utf-8 -*-
"""
Recovery hints: the most specific evidence must win.

A hint that points the wrong way costs a round trip, so these tests pin
the matching order rather than the wording.
"""

import types
import unittest

from forge.core.hinting import render_hints_for_result
from forge.packages.core_ops.search import op as search_op


def fake_op(hints):
    return types.SimpleNamespace(SPEC={'name': 'RUN'}, HINTS=hints)


RUN_LIKE_HINTS = {
    '_max_hints': 1,
    'target': {'message': 'TARGET HINT', 'why': 'target'},
    'exited': {'message': 'EXITED HINT', 'why': 'exited'},
    'no hits': {'message': 'NO HITS HINT', 'why': 'no hits'},
}


class MessageOutranksOutput(unittest.TestCase):

    def test_captured_output_cannot_outrank_the_message(self):
        """The case that sent a test failure to 'RUN needs a file path'."""
        text = render_hints_for_result(fake_op(RUN_LIKE_HINTS), {
            'op': 'RUN',
            'status': 'FAILED_RUNTIME',
            'message': 'Script exited with code 1',
            'preview': 'test_missing_target_does_not_create_a_file ... FAIL',
        })
        self.assertIn('EXITED HINT', text)
        self.assertNotIn('TARGET HINT', text)

    def test_preview_is_still_used_when_the_message_matches_nothing(self):
        text = render_hints_for_result(fake_op(RUN_LIKE_HINTS), {
            'op': 'RUN',
            'status': 'FAILED',
            'message': 'something unrelated',
            'preview': '(no hits)',
        })
        self.assertIn('NO HITS HINT', text)


class EngineStatuses(unittest.TestCase):

    def test_skipped_after_failure_is_not_called_a_failure(self):
        text = render_hints_for_result(fake_op(RUN_LIKE_HINTS), {
            'op': 'WRITE',
            'status': 'SKIPPED_AFTER_FAILURE',
            'message': 'Skipped mutating op after earlier failure: RUN on x.py',
        })
        self.assertIn('earlier operation', text)
        self.assertNotIn('no specific recovery hint', text)

    def test_stale_read_says_to_read_again(self):
        text = render_hints_for_result(fake_op(RUN_LIKE_HINTS), {
            'op': 'WRITE',
            'status': 'SKIPPED_STALE_READ',
            'message': 'File changed since version 00000000 was read',
        })
        self.assertIn('READ the file again', text)


class SearchExpectation(unittest.TestCase):

    def test_failed_expectation_does_not_suggest_fuzzy_matching(self):
        text = render_hints_for_result(search_op, {
            'op': 'SEARCH',
            'status': 'FAILED_EXPECTATION',
            'message': 'EXPECT_HITS >0: found 0 hits',
            'preview': '(no hits)',
        })
        self.assertIn('assertion', text)
        self.assertNotIn('fuzzy', text)


if __name__ == '__main__':
    unittest.main()