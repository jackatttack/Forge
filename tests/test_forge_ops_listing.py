# -*- coding: utf-8 -*-
"""
FORGE ops shows each op's directives, body shape and brief, so a cold
session can see what every op can do without a help call per op.
"""

import unittest

from forge_case import ForgeCase, bundle


class ForgeOpsListing(ForgeCase):

    def ops_preview(self, command='FORGE ops'):
        run = self.run_bundle(bundle(command))
        self.assertEqual(self.statuses(run), ['APPLIED'])
        preview = str(run['results'][0].get('preview') or '')
        # Detail lines wrap; compare with the wrapping undone.
        return ' '.join(preview.split())

    def test_directives_are_listed_under_each_op(self):
        text = self.ops_preview()
        self.assertIn('directives: ACTIVE_ONLY, ASSIGNS', text)
        self.assertIn('GLOB', text)
        self.assertIn('OUTPUT', text)

    def test_body_shape_is_shown_when_a_body_is_allowed(self):
        text = self.ops_preview()
        self.assertIn('body: optional', text)
        self.assertIn('body: required', text)

    def test_briefs_surface_key_capabilities(self):
        text = self.ops_preview()
        self.assertIn('OUTPUT: tail|summary shortens a passing run', text)
        self.assertIn('one pattern per body line', text)
        self.assertIn('MODE: symbols indexes every Python file', text)

    def test_every_public_op_has_a_brief(self):
        run = self.run_bundle(bundle('FORGE ops'))
        rows = run['results'][0]['data']['ops']
        missing = [row['name'] for row in rows if not row.get('brief')]
        self.assertEqual(missing, [], 'public ops without a HELP brief')

    def test_all_installed_listing_also_shows_details(self):
        text = self.ops_preview('FORGE ops all')
        self.assertIn('directives:', text)


if __name__ == '__main__':
    unittest.main()