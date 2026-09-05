# -*- coding: utf-8 -*-
"""Help rendering and structured directive-documentation contracts."""

import unittest

from forge_case import ForgeCase, bundle
from forge_under_test import forge_under_test


forge = forge_under_test()

from forge.packages.core_ops.forge import op as forge_op


class DirectiveDocumentationContract(unittest.TestCase):

    def test_matching_public_and_internal_directives_pass(self):
        issues = (
            forge_op._directive_documentation_issues(
                {
                    'allowed_directives': set([
                        'ARGS',
                        'LIMIT',
                    ]),
                },
                {
                    'directives': {
                        'LIMIT': 'Maximum rows.',
                    },
                    'internal_directives': [
                        'ARGS',
                    ],
                },
            )
        )

        self.assertEqual(
            issues,
            [],
        )

    def test_documented_rejected_directive_fails(self):
        issues = (
            forge_op._directive_documentation_issues(
                {
                    'allowed_directives': set([
                        'LINES',
                    ]),
                },
                {
                    'directives': {
                        'DEPTH': 'Directory depth.',
                    },
                },
            )
        )

        self.assertTrue(
            any(
                'documents rejected directives'
                in issue
                for issue in issues
            ),
            issues,
        )

    def test_accepted_unclassified_directive_fails(self):
        issues = (
            forge_op._directive_documentation_issues(
                {
                    'allowed_directives': set([
                        'LINES',
                        'DOCS',
                    ]),
                },
                {
                    'directives': {
                        'LINES': 'Line range.',
                    },
                },
            )
        )

        self.assertTrue(
            any(
                'leaves directives unclassified'
                in issue
                for issue in issues
            ),
            issues,
        )

    def test_empty_public_description_fails(self):
        issues = (
            forge_op._directive_documentation_issues(
                {
                    'allowed_directives': set([
                        'LIMIT',
                    ]),
                },
                {
                    'directives': {
                        'LIMIT': '',
                    },
                },
            )
        )

        self.assertTrue(
            any(
                'has no description'
                in issue
                for issue in issues
            ),
            issues,
        )

    def test_missing_structured_metadata_fails(self):
        issues = (
            forge_op._directive_documentation_issues(
                {
                    'allowed_directives': set(),
                },
                {},
            )
        )

        self.assertIn(
            'HELP missing directives dict',
            issues,
        )

    def test_public_contract_is_mandatory_but_extensions_opt_in(self):
        self.assertTrue(
            forge_op._directive_documentation_required(
                'FORGE',
                {},
            )
        )

        self.assertFalse(
            forge_op._directive_documentation_required(
                'GIT',
                {},
            )
        )

        self.assertTrue(
            forge_op._directive_documentation_required(
                'GIT',
                {
                    'directives': {},
                },
            )
        )


class ForgeHelpRendering(ForgeCase):

    def help_preview(
        self,
        command,
    ):
        run = self.run_bundle(
            bundle(
                command,
            )
        )

        self.assertEqual(
            self.statuses(run),
            ['APPLIED'],
            run,
        )

        return (
            run['results'][0].get(
                'preview'
            )
            or ''
        )

    def test_quick_help_shows_only_public_directives(self):
        preview = self.help_preview(
            'FORGE help FORGE'
        )

        directives = preview.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'LIMIT',
            directives,
        )

        self.assertNotIn(
            'ARGS',
            directives,
        )

        self.assertNotIn(
            'MODE',
            directives,
        )

    def test_full_help_explains_help_modes(self):
        preview = self.help_preview(
            'FORGE help FORGE full'
        )

        self.assertIn(
            '## Which help do I want?',
            preview,
        )

        self.assertIn(
            'health check, not usage documentation',
            preview,
        )

        self.assertIn(
            'FORGE bundle',
            preview,
        )

    def test_full_help_classifies_parser_directives(self):
        preview = self.help_preview(
            'FORGE help FORGE full'
        )

        self.assertIn(
            'accepted directives: ARGS, LIMIT',
            preview,
        )

        self.assertIn(
            'public directives: LIMIT',
            preview,
        )

        self.assertIn(
            'internal plumbing: ARGS',
            preview,
        )

    def test_contract_passes_for_forge(self):
        preview = self.help_preview(
            'FORGE help FORGE contract'
        )

        self.assertIn(
            'PASS package contract ok',
            preview,
        )

    def test_map_and_read_contracts_pass(self):
        for name in (
            'MAP',
            'READ',
        ):
            preview = self.help_preview(
                'FORGE help %s contract'
                % name
            )

            self.assertIn(
                'PASS package contract ok',
                preview,
            )

    def test_map_full_help_covers_relationships_and_docs(self):
        preview = self.help_preview(
            'FORGE help MAP full'
        )

        self.assertNotIn(
            'forge/forge.packages',
            preview,
        )

        self.assertIn(
            'MODE: relationships',
            preview,
        )

        self.assertIn(
            'DOCS: no',
            preview,
        )

    def test_read_quick_help_lists_only_real_directives(self):
        preview = self.help_preview(
            'FORGE help READ'
        )

        directives = preview.split(
            'DIRECTIVES',
            1,
        )[1]

        for name in (
            'ANCHOR',
            'CONTEXT',
            'DOCS',
            'LINES',
            'MATCH',
            'TARGETS',
        ):
            self.assertIn(
                name,
                directives,
            )

        for name in (
            'ALL',
            'DEPTH',
            'FILES',
            'FILTER',
            'README',
        ):
            self.assertNotIn(
                name,
                directives,
            )

    def test_read_full_help_rejects_directory_assumptions(self):
        preview = self.help_preview(
            'FORGE help READ full'
        )

        self.assertIn(
            'Directories are deliberately not a READ mode',
            preview,
        )

        self.assertIn(
            'MAP docs',
            preview,
        )

    def test_read_directory_target_is_rejected(self):
        run = self.run_bundle(
            bundle(
                'READ .',
            )
        )

        self.assertNotEqual(
            self.statuses(run),
            ['APPLIED'],
            run,
        )

        result = run['results'][0]

        self.assertIn(
            'Use MAP for directories',
            result.get(
                'message',
                '',
            ),
        )

    def test_diff_contract_and_directive_rendering(self):
        contract = self.help_preview(
            'FORGE help DIFF contract'
        )

        self.assertIn(
            'PASS package contract ok',
            contract,
        )

        quick = self.help_preview(
            'FORGE help DIFF'
        )

        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'MODE',
            directives,
        )

        self.assertNotIn(
            'ARGS',
            directives,
        )

        full = self.help_preview(
            'FORGE help DIFF full'
        )

        self.assertIn(
            'accepted directives: ARGS, MODE',
            full,
        )

        self.assertIn(
            'public directives: MODE',
            full,
        )

        self.assertIn(
            'internal plumbing: ARGS',
            full,
        )

        self.assertIn(
            'smoke checks and `FORGE audit`',
            full,
        )
    def test_alias_contract_and_directive_rendering(self):
        contract = self.help_preview(
            'FORGE help ALIAS contract'
        )

        self.assertIn(
            'PASS package contract ok',
            contract,
        )

        quick = self.help_preview(
            'FORGE help ALIAS'
        )

        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'DESCRIPTION',
            directives,
        )

        self.assertIn(
            'HINTS',
            directives,
        )

        self.assertNotIn(
            'ARGS',
            directives,
        )

        self.assertNotIn(
            'PATH_HINTS',
            directives,
        )

        full = self.help_preview(
            'FORGE help ALIAS full'
        )

        self.assertIn(
            '<forge_home>/aliases.json',
            full,
        )

        self.assertIn(
            'readproj tilekit',
            full,
        )

        self.assertIn(
            'internal plumbing: ARGS',
            full,
        )
    def test_branch_and_revert_contracts(self):
        for name in (
            'BRANCH',
            'REVERT',
        ):
            contract = self.help_preview(
                'FORGE help %s contract'
                % name
            )

            self.assertIn(
                'PASS package contract ok',
                contract,
            )

            quick = self.help_preview(
                'FORGE help %s'
                % name
            )

            directives = quick.split(
                'DIRECTIVES',
                1,
            )[1]

            self.assertNotIn(
                'ARGS',
                directives,
            )

            self.assertNotIn(
                'CONFIRM',
                directives,
            )

    def test_branch_full_help_explains_restore_boundaries(self):
        preview = self.help_preview(
            'FORGE help BRANCH full'
        )

        self.assertIn(
            'The body is required for `BRANCH create`.',
            preview,
        )

        self.assertIn(
            'files created after the checkpoint are left alone',
            preview,
        )

        self.assertIn(
            '<storage_root>/branches/<name>/',
            preview,
        )

        self.assertIn(
            'internal plumbing: ARGS',
            preview,
        )

    def test_revert_full_help_explains_drift_and_stamp_rules(self):
        preview = self.help_preview('FORGE help REVERT full')
        for expected in (
            '`latest` is not resolved as shorthand',
            'recovery is refused before mutation',
            'Recovery is not transactional',
            'REVERT never recursively deletes a directory',
            'without explicit existence metadata are refused',
            'its stamp can itself be reverted',
            'internal plumbing: ARGS',
        ):
            self.assertIn(expected, preview)
    def test_url_contract_and_security_documentation(self):
        contract = self.help_preview(
            'FORGE help URL contract'
        )

        self.assertIn(
            'PASS package contract ok',
            contract,
        )

        quick = self.help_preview(
            'FORGE help URL'
        )

        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        for name in (
            'DEST',
            'FOLLOW_REDIRECTS',
            'HEADERS',
            'JPATH',
            'MODE',
            'STRIP',
            'TIMEOUT',
        ):
            self.assertIn(
                name,
                directives,
            )

        self.assertNotIn(
            'CONFIRM',
            directives,
        )

        full = self.help_preview(
            'FORGE help URL full'
        )

        self.assertIn(
            'JPATH: data.items.0.title',
            full,
        )

        self.assertIn(
            'Forge stores submitted bundles in run history',
            full,
        )

        self.assertIn(
            'Never put an Authorization header',
            full,
        )

        self.assertIn(
            'capped at 80 output lines',
            full,
        )
    def test_search_contract_and_full_help_cleanup(self):
        contract = self.help_preview(
            'FORGE help SEARCH contract'
        )

        self.assertIn(
            'PASS package contract ok',
            contract,
        )

        full = self.help_preview(
            'FORGE help SEARCH full'
        )

        self.assertIn(
            'Prefer the path-first form',
            full,
        )

        self.assertIn(
            '### Python AST selectors',
            full,
        )

        self.assertNotIn(
            'reboot search op',
            full,
        )

        self.assertNotIn(
            'future dependency-focused op',
            full,
        )

    def test_insert_contract_and_repeated_anchor_guidance(self):
        contract = self.help_preview(
            'FORGE help INSERT contract'
        )

        self.assertIn(
            'PASS package contract ok',
            contract,
        )

        quick = self.help_preview(
            'FORGE help INSERT'
        )

        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        for name in (
            'ANCHOR',
            'CONFIRM',
            'EXPECT',
            'INDENT',
            'LINE',
            'MATCH',
            'OCCURRENCE',
            'POSITION',
        ):
            self.assertIn(
                name,
                directives,
            )

        full = self.help_preview(
            'FORGE help INSERT full'
        )

        self.assertIn(
            '## Whitespace',
            full,
        )

        self.assertIn(
            '`OCCURRENCE: 2` alone fails',
            full,
        )

        self.assertNotIn(
            'INSERT_BEFORE',
            full,
        )

    def test_insert_occurrence_requires_matching_expect(self):
        from forge.packages.core_ops.insert import (
            op as insert_op,
        )

        index, error = insert_op._anchor_index(
            [
                'print("same")',
                'print("same")',
            ],
            'print("same")',
            'exact',
            2,
            1,
        )

        self.assertIsNone(
            index,
        )

        self.assertIn(
            'matched 2 times, expected 1',
            error,
        )

        index, error = insert_op._anchor_index(
            [
                'print("same")',
                'print("same")',
            ],
            'print("same")',
            'exact',
            2,
            2,
        )

        self.assertEqual(
            index,
            1,
        )

        self.assertIsNone(
            error,
        )
    def test_replace_delete_and_write_contracts(self):
        for name in (
            'REPLACE',
            'DELETE',
            'WRITE',
        ):
            contract = self.help_preview(
                'FORGE help %s contract'
                % name
            )

            self.assertIn(
                'PASS package contract ok',
                contract,
            )

    def test_replace_full_help_explains_ast_and_exact_modes(self):
        preview = self.help_preview(
            'FORGE help REPLACE full'
        )

        self.assertIn(
            '`SomeClass.*` selects the complete class definition',
            preview,
        )

        self.assertIn(
            'REPLACE has no fuzzy block mode',
            preview,
        )

        self.assertIn(
            '`ALL: yes` requires `CONFIRM: yes`',
            preview,
        )

        self.assertNotIn(
            'reboot unified',
            preview,
        )

    def test_replace_all_requires_confirmation(self):
        from forge.packages.core_ops.replace import (
            op as replace_op,
        )

        parsed = {
            'target': 'example.txt',
            'directives': {
                'ALL': 'yes',
            },
            'blocks': {
                'OLD': 'old',
                'NEW': 'new',
            },
            'body': '',
        }

        errors = replace_op.validate(
            parsed
        )

        self.assertIn(
            'REPLACE ALL: yes requires CONFIRM: yes',
            errors,
        )

        parsed['directives']['CONFIRM'] = (
            'yes'
        )

        self.assertNotIn(
            'REPLACE ALL: yes requires CONFIRM: yes',
            replace_op.validate(
                parsed
            ),
        )

    def test_delete_full_help_states_file_only_recovery(self):
        preview = self.help_preview(
            'FORGE help DELETE full'
        )

        self.assertIn(
            'DELETE refuses directory paths',
            preview,
        )

        self.assertIn(
            'A precise whole-file path does not require confirmation',
            preview,
        )

        self.assertIn(
            'REVERT operates on the entire recorded run',
            preview,
        )

    def test_write_full_help_distinguishes_confirmation_value(self):
        preview = self.help_preview(
            'FORGE help WRITE full'
        )

        self.assertIn(
            'The overwrite value is the literal word `overwrite`.',
            preview,
        )

        self.assertIn(
            'substitute for full-file replacement.',
            preview,
        )

        self.assertIn(
            'deliberately invalid fixture',
            preview,
        )

        quick = self.help_preview(
            'FORGE help WRITE'
        )

        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'ALLOW_BROKEN',
            directives,
        )

        self.assertIn(
            'CONFIRM',
            directives,
        )
    def test_copy_and_run_contracts(self):
        copy_contract = self.help_preview(
            'FORGE help COPY contract'
        )
        run_contract = self.help_preview(
            'FORGE help RUN contract'
        )

        self.assertIn(
            'CONTRACT\nPASS package contract ok',
            copy_contract,
        )
        self.assertIn(
            'CONTRACT\nPASS package contract ok',
            run_contract,
        )

    def test_copy_help_is_file_only_and_uses_overwrite(self):
        preview = self.help_preview(
            'FORGE help COPY full'
        )

        self.assertIn(
            'It does not copy directories',
            preview,
        )
        self.assertIn(
            'COPY has no',
            preview,
        )
        self.assertIn(
            '`CONFIRM` directive.',
            preview,
        )
        self.assertIn(
            'A precise whole-file DELETE does not require confirmation',
            preview,
        )

        quick = self.help_preview(
            'FORGE help COPY'
        )
        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'TO',
            directives,
        )
        self.assertIn(
            'OVERWRITE',
            directives,
        )
        self.assertNotIn(
            'CONFIRM',
            directives,
        )

    def test_run_help_states_in_process_boundaries(self):
        preview = self.help_preview(
            'FORGE help RUN full'
        )

        self.assertIn(
            'current Python process',
            preview,
        )
        self.assertIn(
            'Imported modules remain in',
            preview,
        )
        self.assertIn(
            'RUN does not truncate stdout or stderr',
            preview,
        )
        self.assertIn(
            'Do not RUN a Forge entrypoint',
            preview,
        )
        self.assertIn(
            'does not infer or record arbitrary filesystem changes',
            preview,
        )

        quick = self.help_preview(
            'FORGE help RUN'
        )
        directives = quick.split(
            'DIRECTIVES',
            1,
        )[1]

        self.assertIn(
            'ARGS',
            directives,
        )
        self.assertIn(
            'CONFIRM',
            directives,
        )
    def test_every_public_op_passes_help_contract(self):
        names = [
            'FORGE',
            'MAP',
            'READ',
            'SEARCH',
            'WRITE',
            'REPLACE',
            'INSERT',
            'DELETE',
            'COPY',
            'RUN',
            'DIFF',
            'REVERT',
            'BRANCH',
            'URL',
            'ALIAS',
        ]

        for name in names:
            preview = self.help_preview(
                'FORGE help %s contract'
                % name
            )

            self.assertIn(
                'CONTRACT\nPASS package contract ok',
                preview,
                name,
            )
if __name__ == '__main__':
    unittest.main(
        verbosity=2
    )