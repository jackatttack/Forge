# -*- coding: utf-8 -*-
"""
What Forge accepts at bundle command level.

The rule: outside BEGIN_/END_ blocks a bundle may contain only blank
lines, known op headers, and DIRECTIVE: value lines. Anything else is a
parse error, and a parse error means no operation executes.

This exists because unrecognised text used to be appended silently to
the preceding operation's body, even after that body's END_BODY had
closed. A mistyped op name did not fail; it became data inside a
mutating operation, and the packet still said APPLIED. Silent
misreporting is the one failure Forge's contract cannot tolerate, so
these tests pin the strict behaviour in place.
"""

import unittest

from forge_case import ForgeCase, bundle


class UnknownOpIsRefused(ForgeCase):

    def test_typo_op_alone_fails_to_parse(self):
        """An unknown op as the only operation must fail the bundle."""
        run = self.run_bundle(
            bundle(
                'REPLCE app.py',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertEqual(run.get('results') or [], [])

    def test_typo_op_after_valid_op_prevents_all_execution(self):
        """
        A later typo must stop the earlier operation from running.

        The whole bundle is parsed before anything executes, so a
        mistake anywhere refuses everything.
        """
        run = self.run_bundle(
            bundle(
                'WRITE created.txt',
                'BEGIN_BODY',
                'content',
                'END_BODY',
                '',
                'REPLCE app.py',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertEqual(run.get('results') or [], [])
        self.assertFalse(self.exists('created.txt'))

    def test_typo_after_end_body_is_not_swallowed(self):
        """
        A typo after END_BODY must not become part of that body.

        Previously this text was appended to the closed body, so the
        file was written with content the user never asked for.
        """
        run = self.run_bundle(
            bundle(
                'WRITE created.txt',
                'BEGIN_BODY',
                'content',
                'END_BODY',
                'REPLCE app.py',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertFalse(self.exists('created.txt'))

        joined = '\n'.join(str(e) for e in (run.get('errors') or []))
        self.assertIn('REPLCE', joined)

    def test_prose_between_operations_is_refused(self):
        """Bundles carry operations, not commentary."""
        run = self.run_bundle(
            bundle(
                'READ notes.txt',
                '',
                'now let us look at the other file',
                '',
                'READ other.txt',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertEqual(run.get('results') or [], [])


class BlockContentStaysLiteral(ForgeCase):

    def test_op_looking_text_inside_body_is_data(self):
        """
        Text inside BEGIN_BODY is content, never parsed as operations.

        Forge edits its own documentation and tests, both of which are
        full of Forge syntax, so this has to hold.
        """
        run = self.run_bundle(
            bundle(
                'WRITE guide.txt',
                'BEGIN_BODY',
                'To replace code, write:',
                '',
                'REPLACE app.py::main',
                'BEGIN_BODY',
                'def main():',
                '    return True',
                'END_BODY',
            )
        )

        self.assertEqual(self.statuses(run)[0], 'APPLIED')

        written = self.get('guide.txt')

        self.assertIn('REPLACE app.py::main', written)
        self.assertIn('def main():', written)
        self.assertFalse(self.exists('app.py'))


class ValidBundlesStillParse(ForgeCase):

    def test_multi_op_bundle_parses(self):
        """The strict rule must not reject ordinary bundles."""
        self.put('notes.txt', 'hello\n')

        run = self.run_bundle(
            bundle(
                'READ notes.txt',
                '',
                'WRITE second.txt',
                'BEGIN_BODY',
                'content',
                'END_BODY',
                '',
                'READ second.txt',
            )
        )

        self.assertEqual(run.get('errors') or [], [])
        self.assertEqual(len(run.get('results') or []), 3)
        self.assertEqual(self.statuses(run), ['APPLIED'] * 3)

    def test_directives_and_blank_lines_are_accepted(self):
        self.put('notes.txt', 'a\nb\nc\nd\n')

        run = self.run_bundle(
            bundle(
                'READ notes.txt',
                'LINES: 1-2',
                '',
                '',
                'MAP .',
                'DEPTH: 1',
            )
        )

        self.assertEqual(run.get('errors') or [], [])
        self.assertEqual(self.statuses(run), ['APPLIED', 'APPLIED'])


class ImplicitBodyIsNoLongerAccepted(ForgeCase):
    """
    Body content without BEGIN_BODY / END_BODY is refused.

    An audit of the repository found no documentation, example, hint, or
    boot text that used the unwrapped form: every WRITE example in the
    op packages uses explicit markers. The permissive fallback existed
    only as parser inheritance, and its practical effect was to swallow
    typos. This is a deliberate breaking change to the command language.
    """

    def test_write_without_markers_fails(self):
        run = self.run_bundle(
            bundle(
                'WRITE created.txt',
                'content with no markers',
            )
        )

        self.assertTrue(run.get('errors'))
        self.assertFalse(self.exists('created.txt'))


if __name__ == '__main__':
    unittest.main(verbosity=2)