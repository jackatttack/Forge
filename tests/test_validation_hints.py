# -*- coding: utf-8 -*-
"""
Validation failures with no op-specific hint get a hint built from the rule.

The validation message already names the rule, so the hint leads with it
and quotes the help for each directive it mentions, instead of the generic
"no specific recovery hint matched".
"""

import types
import unittest

import forge_case  # noqa: F401  (puts the checkout Forge on sys.path)
from forge.core.hinting import render_hints_for_result


GENERIC = 'no specific recovery hint matched'


def fake_op(hints=None, directives=None):
    return types.SimpleNamespace(
        SPEC={'name': 'REPLACE'},
        HINTS=hints or {},
        HELP={'directives': directives or {}},
    )


REPLACE_LIKE_DIRECTIVES = {
    'ALL': 'Replace every matching block.',
    'CONFIRM': 'Confirm an edit that needs it,\n    such as ALL: yes.',
    'OCCURRENCE': 'Replace only the Nth match.',
}


class ValidationRuleHints(unittest.TestCase):

    def hint_for(self, message, status='FAILED_PARSE', hints=None):
        return render_hints_for_result(
            fake_op(hints, REPLACE_LIKE_DIRECTIVES),
            {'op': 'REPLACE', 'status': status, 'message': message},
        )

    def test_rule_leads_and_named_directives_are_explained(self):
        text = self.hint_for('REPLACE ALL: yes requires CONFIRM: yes')
        self.assertIn('RULE: REPLACE ALL: yes requires CONFIRM: yes', text)
        self.assertIn('- ALL: Replace every matching block.', text)
        self.assertIn('- CONFIRM: Confirm an edit that needs it, such as ALL: yes.', text)
        self.assertLess(text.index('- ALL:'), text.index('- CONFIRM:'))
        self.assertNotIn('OCCURRENCE', text)
        self.assertIn('FORGE help REPLACE full', text)
        self.assertNotIn(GENERIC, text)

    def test_rule_without_known_directives_still_leads(self):
        text = self.hint_for('REPLACE requires a target path')
        self.assertIn('RULE: REPLACE requires a target path', text)
        self.assertNotIn('DIRECTIVES:', text)

    def test_a_matching_op_hint_still_wins(self):
        text = self.hint_for(
            'REPLACE ALL: yes requires CONFIRM: yes',
            hints={'requires confirm': {'message': 'SPECIFIC HINT', 'why': 'x'}},
        )
        self.assertIn('SPECIFIC HINT', text)
        self.assertNotIn('RULE:', text)

    def test_other_failures_keep_the_generic_hint(self):
        text = self.hint_for('something broke', status='FAILED')
        self.assertIn(GENERIC, text)
        self.assertNotIn('RULE:', text)


if __name__ == '__main__':
    unittest.main()