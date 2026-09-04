# -*- coding: utf-8 -*-
"""Strict whole-submission Markdown fence support."""

import unittest

from forge_case import ForgeCase, bundle


class MarkdownFenceBundles(ForgeCase):

    def test_plain_fenced_bundle_runs(self):
        run = self.run_bundle(
            bundle(
                '```',
                'WRITE fenced.txt',
                'BEGIN_BODY',
                'worked',
                'END_BODY',
                '```',
            )
        )

        self.assertEqual(
            self.statuses(run),
            ['APPLIED'],
            run,
        )
        self.assertEqual(
            self.get('fenced.txt'),
            'worked',
        )
        self.assertEqual(
            run.get(
                'unwrapped_markdown_fence'
            ),
            'plain',
        )

    def test_supported_fence_labels_run(self):
        for label in (
            'forge',
            'text',
            'plaintext',
        ):
            run = self.run_bundle(
                bundle(
                    '```' + label,
                    'FORGE ops',
                    '```',
                )
            )

            self.assertEqual(
                self.statuses(run),
                ['APPLIED'],
                label,
            )
            self.assertEqual(
                run.get(
                    'unwrapped_markdown_fence'
                ),
                label,
            )

    def test_surrounding_prose_is_not_discarded(self):
        run = self.run_bundle(
            bundle(
                'Here is the bundle:',
                '```',
                'WRITE refused.txt',
                'BEGIN_BODY',
                'no',
                'END_BODY',
                '```',
            )
        )

        self.assertTrue(
            run.get('errors'),
            run,
        )
        self.assertFalse(
            self.exists('refused.txt')
        )

    def test_unsupported_label_is_refused(self):
        run = self.run_bundle(
            bundle(
                '```python',
                'WRITE refused.txt',
                'BEGIN_BODY',
                'no',
                'END_BODY',
                '```',
            )
        )

        self.assertTrue(
            run.get('errors'),
            run,
        )
        self.assertFalse(
            self.exists('refused.txt')
        )

    def test_multiple_top_level_fences_are_refused(self):
        run = self.run_bundle(
            bundle(
                '```',
                'WRITE first.txt',
                'BEGIN_BODY',
                'one',
                'END_BODY',
                '```',
                '',
                '```',
                'WRITE second.txt',
                'BEGIN_BODY',
                'two',
                'END_BODY',
                '```',
            )
        )

        self.assertTrue(
            run.get('errors'),
            run,
        )
        self.assertFalse(
            self.exists('first.txt')
        )
        self.assertFalse(
            self.exists('second.txt')
        )

    def test_malformed_inner_bundle_is_refused_atomically(self):
        run = self.run_bundle(
            bundle(
                '```forge',
                'WRITE first.txt',
                'BEGIN_BODY',
                'one',
                'END_BODY',
                '',
                'REPLCE second.txt',
                '```',
            )
        )

        self.assertTrue(
            run.get('errors'),
            run,
        )
        self.assertFalse(
            self.exists('first.txt')
        )


if __name__ == '__main__':
    unittest.main(
        verbosity=2
    )