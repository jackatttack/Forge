# -*- coding: utf-8 -*-
"""Resolving an operation's declared effect into its gating policy."""

import types
import unittest

import forge_case  # noqa: F401  (puts the Forge under test on sys.path)
from forge.core.operation_policy import (
    resolve_policy, subcommand_word, READ, WORKSPACE, UNKNOWN,
)


def module(**attributes):
    return types.SimpleNamespace(**attributes)


class DeclaredEffects(unittest.TestCase):

    def test_constant_declaration(self):
        policy = resolve_policy(module(EFFECT='read'), {})
        self.assertEqual(policy['effect'], READ)
        self.assertTrue(policy['runs_after_failure'])
        self.assertFalse(policy['own_failure_blocks'])

    def test_function_declaration_sees_the_subcommand(self):
        def effect(parsed_op):
            return 'read' if subcommand_word(parsed_op) == 'list' else 'workspace'
        op = module(effect=effect)
        self.assertEqual(resolve_policy(op, {'target': 'list'})['effect'], READ)
        self.assertEqual(
            resolve_policy(op, {'target': 'restore x'})['effect'], WORKSPACE)

    def test_effectful_op_blocks_and_is_gated(self):
        policy = resolve_policy(module(EFFECT='workspace'), {})
        self.assertFalse(policy['runs_after_failure'])
        self.assertTrue(policy['own_failure_blocks'])

    def test_own_failure_can_be_an_observation(self):
        policy = resolve_policy(
            module(EFFECT='execute', OWN_FAILURE_BLOCKS=False), {})
        self.assertFalse(policy['runs_after_failure'])
        self.assertFalse(policy['own_failure_blocks'])


class FailsClosed(unittest.TestCase):

    def assert_unknown(self, op):
        policy = resolve_policy(op, {})
        self.assertEqual(policy['effect'], UNKNOWN)
        self.assertFalse(policy['runs_after_failure'])
        self.assertTrue(policy['own_failure_blocks'])

    def test_no_declaration(self):
        self.assert_unknown(module())

    def test_unrecognised_value(self):
        self.assert_unknown(module(EFFECT='harmless'))

    def test_raising_declaration(self):
        def effect(parsed_op):
            raise RuntimeError('boom')
        self.assert_unknown(module(effect=effect))

    def test_missing_module(self):
        self.assert_unknown(None)


class SubcommandWord(unittest.TestCase):

    def test_args_win_over_target(self):
        parsed = {'target': 'ignored', 'directives': {'ARGS': 'Upload --x'}}
        self.assertEqual(subcommand_word(parsed), 'upload')

    def test_target_when_no_args(self):
        self.assertEqual(subcommand_word({'target': 'create before'}), 'create')

    def test_empty(self):
        self.assertEqual(subcommand_word({}), '')


if __name__ == '__main__':
    unittest.main()