# -*- coding: utf-8 -*-
"""
What the core guard currently protects.

The guard exists to stop Forge from casually rewriting its own runtime.
These tests describe its behaviour as it stands, including the parts
that look wrong, so that correcting the protected paths is a visible
deliberate change rather than a silent one.
"""

import unittest

from forge_under_test import forge_under_test

forge_under_test()

from forge.core import core_guard


class ProtectedPaths(unittest.TestCase):
    """
    CURRENT BEHAVIOUR, believed wrong.

    PROTECTED_PREFIXES describes a 'forge/forge/core/' layout that
    exists in neither the repository nor the installed runtime, so the
    guard protects nothing in practice.

    When the prefixes are corrected, the first test should assert True
    and the second should be removed.
    """

    def test_guard_does_not_cover_the_current_layout(self):
        self.assertFalse(
            core_guard.target_is_protected('forge/core/engine.py')
        )

    def test_guard_still_covers_the_legacy_layout(self):
        self.assertTrue(
            core_guard.target_is_protected('forge/forge/core/engine.py')
        )

    def test_unprotected_paths_are_unprotected(self):
        self.assertFalse(
            core_guard.target_is_protected('projects/example/app.py')
        )


class MutationClassification(unittest.TestCase):

    def test_run_is_classified_mutating(self):
        """RUN executes arbitrary Python and is mutating by definition."""
        self.assertTrue(core_guard.is_mutating_op('RUN'))

    def test_read_only_ops_are_not_mutating(self):
        for op_name in ('READ', 'MAP', 'SEARCH', 'DIFF', 'FORGE'):
            self.assertFalse(
                core_guard.is_mutating_op(op_name),
                msg='%s should not be mutating' % op_name,
            )

    def test_unknown_ops_are_not_classified_mutating(self):
        """
        CURRENT BEHAVIOUR, worth noting.

        Classification is a fixed name list, so an unknown or
        host-provided mutating op is treated as non-mutating. This is
        the leak that moving policy into the op contract should close.
        """
        self.assertFalse(core_guard.is_mutating_op('SOMEEXTENSION'))


class ConfirmDirective(unittest.TestCase):

    def test_confirm_values_are_accepted(self):
        for value in ('yes', 'true', '1', 'confirm', 'overwrite'):
            self.assertTrue(
                core_guard.has_confirm(
                    {'directives': {'CONFIRM': value}}
                ),
                msg='CONFIRM: %s should count as confirmation' % value,
            )

    def test_missing_confirm_is_not_confirmation(self):
        self.assertFalse(core_guard.has_confirm({'directives': {}}))


if __name__ == '__main__':
    unittest.main(verbosity=2)