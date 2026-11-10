# -*- coding: utf-8 -*-
"""
Alias placeholders are filled in one pass.

$1 used to be replaced before $10, so the tenth word came out as the
first word followed by a 0, and a word that looked like a placeholder
was expanded a second time.
"""

import unittest

import forge_case  # noqa: F401  (puts the Forge under test on the path)

from forge.core.preparse import substitute_alias_args


class AliasPlaceholders(unittest.TestCase):

    def test_tenth_word_is_not_the_first_word_and_a_zero(self):
        words = 'a b c d e f g h i j'
        self.assertEqual(substitute_alias_args('RUN $10', words), 'RUN j')

    def test_a_word_that_looks_like_a_placeholder_is_left_alone(self):
        self.assertEqual(
            substitute_alias_args('SAY $1 $2', '$2 x'),
            'SAY $2 x',
        )

    def test_all_last_and_all_but_last(self):
        self.assertEqual(
            substitute_alias_args('A $* | $-1 | $^', 'x y z'),
            'A x y z | z | x y',
        )

    def test_missing_positional_word_becomes_empty(self):
        self.assertEqual(substitute_alias_args('A $1$3', 'x'), 'A x')

    def test_placeholders_need_words(self):
        with self.assertRaises(ValueError):
            substitute_alias_args('A $1', '')

    def test_plain_expansion_is_unchanged(self):
        self.assertEqual(substitute_alias_args('MAP .', ''), 'MAP .')


if __name__ == '__main__':
    unittest.main()