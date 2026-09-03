# -*- coding: utf-8 -*-
"""
FORGE bundle and the bundle syntax guide.

The guide ships inside the package so the installed runtime is always
the authority on its own grammar, the same arrangement as FIRST_BOOT.txt
and FORGE help <OP>. A guide that documents a different version of the
language than the parser implements would be worse than none at all.
"""

import unittest

from forge_case import ForgeCase, bundle
from forge_under_test import forge_under_test

forge = forge_under_test()


class PublicApi(unittest.TestCase):

    def test_bundle_syntax_text_is_exported(self):
        self.assertIn('bundle_syntax_text', forge.__all__)

    def test_bundle_syntax_text_returns_the_guide(self):
        text = forge.bundle_syntax_text()

        self.assertIn('FORGE BUNDLE SYNTAX', text)
        self.assertIn('BEGIN_BODY', text)

    def test_boot_and_bundle_are_different_documents(self):
        self.assertNotEqual(
            forge.bundle_syntax_text(),
            forge.first_boot_text(),
        )


class BundleCommand(ForgeCase):

    def test_forge_bundle_returns_the_guide(self):
        run = self.run_bundle(
            bundle(
                'FORGE bundle',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])

        result = run['results'][0]

        self.assertEqual(result['data'].get('mode'), 'bundle')
        self.assertIn('FORGE BUNDLE SYNTAX', result.get('preview') or '')

    def test_forge_bundle_rejects_arguments(self):
        run = self.run_bundle(
            bundle(
                'FORGE bundle extra',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')

    def test_forge_boot_still_works(self):
        """The new subcommand must not disturb the existing one."""
        run = self.run_bundle(
            bundle(
                'FORGE boot',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertEqual(run['results'][0]['data'].get('mode'), 'boot')


class OpCountIsUnchanged(ForgeCase):
    """
    FORGE bundle is a subcommand, not a new operation.

    CI asserts an exact set of 15 public ops, so a subcommand that
    accidentally registered as an op would break the release job. This
    catches that earlier and more clearly.
    """

    def test_still_fifteen_public_ops(self):
        run = self.run_bundle(
            bundle(
                'FORGE ops',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])

        rows = (run['results'][0].get('data') or {}).get('ops') or []
        names = set(str(row.get('name') or '').upper() for row in rows)

        self.assertEqual(
            names,
            set([
                'ALIAS', 'BRANCH', 'COPY', 'DELETE', 'DIFF',
                'FORGE', 'INSERT', 'MAP', 'READ', 'REPLACE',
                'REVERT', 'RUN', 'SEARCH', 'URL', 'WRITE',
            ]),
        )


class GuideMatchesTheParser(ForgeCase):
    """
    The guide's own examples must behave as the guide says.

    Documentation drifting from the parser is the failure this file
    exists to prevent, so the two worked examples are executed rather
    than trusted.
    """

    def test_documented_parse_failure_actually_fails(self):
        """The REPLCE example in the guide must refuse the bundle."""
        run = self.run_bundle(
            bundle(
                'WRITE notes.txt',
                'BEGIN_BODY',
                'hello',
                'END_BODY',
                '',
                'REPLCE app.py',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertFalse(self.exists('notes.txt'))

    def test_documented_literal_body_stays_literal(self):
        """The guide's nested-syntax example must write, not execute."""
        run = self.run_bundle(
            bundle(
                'WRITE guide.txt',
                'BEGIN_BODY',
                'To replace a function, write:',
                '',
                'REPLACE app.py::main',
                'BEGIN_BODY',
                'def main():',
                '    return True',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run), ['APPLIED'])
        self.assertIn('REPLACE app.py::main', self.get('guide.txt'))
        self.assertFalse(self.exists('app.py'))


if __name__ == '__main__':
    unittest.main(verbosity=2)