# -*- coding: utf-8 -*-
"""Tagged block markers: BEGIN_BODY @tag closes only at END_BODY @tag.

A tagged block treats bare markers inside it as plain text, so a bundle can
write or edit text that itself contains Forge block markers, such as a
stored bundle being repaired before FORGE rerun.
"""

import unittest

from forge_case import ForgeCase, bundle


class TaggedBlocks(ForgeCase):

    def test_tagged_body_keeps_bare_markers_as_text(self):
        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY @raw',
                'first line',
                'END_BODY',
                'BEGIN_OLD',
                'END_BODY @raw',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(
            self.get('notes.txt'),
            'first line\nEND_BODY\nBEGIN_OLD',
        )

    def test_tagged_old_and_new_can_edit_marker_lines(self):
        run = self.run_bundle(
            bundle(
                'WRITE stored.txt',
                'BEGIN_BODY @raw',
                'WRITE target.txt',
                'BEGIN_BODY',
                'content',
                'END_BODY @raw',
                'REPLACE stored.txt',
                'BEGIN_OLD @fix',
                'BEGIN_BODY',
                'content',
                'END_OLD @fix',
                'BEGIN_NEW @fix',
                'BEGIN_BODY',
                'content',
                'END_BODY',
                'END_NEW @fix',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED', 'APPLIED'], run)
        self.assertEqual(
            self.get('stored.txt'),
            'WRITE target.txt\nBEGIN_BODY\ncontent\nEND_BODY',
        )

    def test_tagged_old_may_contain_partner_markers(self):
        run = self.run_bundle(
            bundle(
                'WRITE partner.txt',
                'BEGIN_BODY @raw',
                'BEGIN_NEW',
                'x',
                'END_BODY @raw',
                'REPLACE partner.txt',
                'BEGIN_OLD @fix',
                'BEGIN_NEW',
                'x',
                'END_OLD @fix',
                'BEGIN_NEW',
                'y',
                'END_NEW',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED', 'APPLIED'], run)
        self.assertEqual(self.get('partner.txt'), 'y')

    def test_missing_tagged_end_names_the_tag(self):
        run = self.run_bundle(
            bundle(
                'WRITE lost.txt',
                'BEGIN_BODY @raw',
                'text',
                'END_BODY',
            )
        )

        self.assertEqual(run.get('status'), 'FAILED_PARSE', run)
        self.assertIn('END_BODY @raw', '\n'.join(run.get('errors') or []))

    def test_other_tag_does_not_close_the_block(self):
        run = self.run_bundle(
            bundle(
                'WRITE mixed.txt',
                'BEGIN_BODY @a',
                'x',
                'END_BODY @b',
                'END_BODY @a',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(self.get('mixed.txt'), 'x\nEND_BODY @b')

    def test_untagged_block_is_unchanged(self):
        run = self.run_bundle(
            bundle(
                'WRITE plain.txt',
                'BEGIN_BODY',
                'END_BODY @raw',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'], run)
        self.assertEqual(self.get('plain.txt'), 'END_BODY @raw')


if __name__ == '__main__':
    unittest.main()
