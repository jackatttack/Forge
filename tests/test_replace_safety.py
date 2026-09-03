# -*- coding: utf-8 -*-
"""
REPLACE must never leave a file half-edited.

A refused mutation should leave the original bytes untouched, because
the whole Forge contract depends on a failed packet meaning nothing
happened.
"""

import unittest

from forge_case import ForgeCase, bundle


class ReplaceLeavesSourceIntact(ForgeCase):

    def test_anchor_mismatch_does_not_touch_the_file(self):
        """A missing OLD block must leave the file byte-identical."""
        original = 'value = 1\n'
        self.put('config.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE config.py',
                'BEGIN_OLD',
                'value = 99',
                'END_OLD',
                'BEGIN_NEW',
                'value = 2',
                'END_NEW',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.get('config.py'), original)

    def test_compile_failure_does_not_touch_the_file(self):
        """Invalid Python must be refused before anything is written."""
        original = 'def main():\n    return True\n'
        self.put('app.py', original)

        run = self.run_bundle(
            bundle(
                'REPLACE app.py::main',
                'BEGIN_BODY',
                'def main(:',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertEqual(self.get('app.py'), original)

    def test_missing_target_does_not_create_a_file(self):
        """REPLACE on an absent file must not create it."""
        run = self.run_bundle(
            bundle(
                'REPLACE absent.py::main',
                'BEGIN_BODY',
                'def main():',
                '    return True',
                'END_BODY',
            )
        )

        self.assertNotEqual(self.statuses(run)[0], 'APPLIED')
        self.assertFalse(self.exists('absent.py'))


if __name__ == '__main__':
    unittest.main(verbosity=2)