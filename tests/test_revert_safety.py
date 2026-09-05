# -*- coding: utf-8 -*-
"""Recovery must preserve newer work and record its own changes."""

import os
import shutil
import unittest

from forge_case import ForgeCase, bundle, forge
from forge.core import run_storage


def replace_text(path, old, new):
    return bundle(
        'REPLACE ' + path,
        'BEGIN_OLD',
        old,
        'END_OLD',
        'BEGIN_NEW',
        new,
        'END_NEW',
    )


class RevertSafety(ForgeCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(shutil.rmtree, self.project_root)

    def stored_run(self, text):
        return forge.run_text(
            text,
            project_root=self.project_root,
            forge_home=self.forge_home,
            mode='dev',
            store=True,
        )

    def applied_run(self, text):
        run = self.stored_run(text)
        self.assertEqual(
            run['status'], 'APPLIED',
            msg=repr(run.get('errors')),
        )
        return run

    def revert(self, original):
        return self.stored_run('REVERT ' + original['stamp'])

    def test_clean_revert_is_recorded_and_can_itself_be_reverted(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run(
            replace_text('a.txt', 'original', 'edited')
        )
        recovery = self.revert(original)
        self.assertEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original\n')
        self.assertTrue(
            recovery.get('touched_files'),
            'REVERT must record the contents it displaced',
        )

        redo = self.revert(recovery)
        self.assertEqual(redo['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'edited\n')

    def test_later_conflict_prevents_all_restoration(self):
        self.put('a.txt', 'original a\n')
        self.put('b.txt', 'original b\n')
        original = self.applied_run(
            replace_text('a.txt', 'original a', 'edited a')
            + '\n\n'
            + replace_text('b.txt', 'original b', 'edited b')
        )
        self.put('b.txt', 'new independent work\n')

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'edited a\n')
        self.assertEqual(self.get('b.txt'), 'new independent work\n')
        self.assertFalse(recovery.get('touched_files'))

    def test_created_file_replaced_by_directory_is_preserved(self):
        original = self.applied_run(bundle(
            'WRITE created.txt',
            'BEGIN_BODY',
            'created',
            'END_BODY',
        ))
        path = os.path.join(self.project_root, 'created.txt')
        os.remove(path)
        os.mkdir(path)
        self.put('created.txt/new.txt', 'new work\n')

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(self.get('created.txt/new.txt'), 'new work\n')

    def test_deleted_file_is_restored_when_still_absent(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run('DELETE a.txt')
        self.assertFalse(self.exists('a.txt'))

        recovery = self.revert(original)
        self.assertEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original\n')

    def test_deleted_file_recreated_empty_is_a_conflict(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run('DELETE a.txt')
        self.put('a.txt', '')

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), '')

    def test_empty_file_removed_after_edit_is_a_conflict(self):
        self.put('a.txt', 'original')
        original = self.applied_run(
            replace_text('a.txt', 'original', '')
        )
        self.assertEqual(self.get('a.txt'), '')
        os.remove(os.path.join(self.project_root, 'a.txt'))

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertFalse(self.exists('a.txt'))

    def test_two_edits_record_original_and_final_contents(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run(
            replace_text('a.txt', 'original', 'middle')
            + '\n\n'
            + replace_text('a.txt', 'middle', 'final')
        )
        manifest, error = run_storage.read_manifest(
            self.project_root,
            original['stamp'],
            environment=original['environment'],
        )
        self.assertIsNone(error)
        self.assertEqual(len(manifest['touched']), 1)
        self.assertEqual(manifest['touched'][0]['before'], 'original\n')
        self.assertEqual(manifest['touched'][0]['after'], 'final\n')

        recovery = self.revert(original)
        self.assertEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original\n')

    def test_bad_snapshot_prevents_all_restoration(self):
        self.put('a.txt', 'original a\n')
        self.put('b.txt', 'original b\n')
        original = self.applied_run(
            replace_text('a.txt', 'original a', 'edited a')
            + '\n\n'
            + replace_text('b.txt', 'original b', 'edited b')
        )
        snapshot = os.path.join(
            original['artifact_dir'], 'snapshots', 'b.txt',
        )
        with open(snapshot, 'w', encoding='utf-8') as handle:
            handle.write('damaged snapshot\n')

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'edited a\n')
        self.assertEqual(self.get('b.txt'), 'edited b\n')
    def test_created_file_can_be_recovered_and_recreated(self):
        original = self.applied_run(bundle(
            'WRITE a.txt',
            'BEGIN_BODY',
            'created',
            'END_BODY',
        ))
        contents = self.get('a.txt')
        recovery = self.revert(original)
        self.assertEqual(recovery['status'], 'APPLIED')
        self.assertFalse(self.exists('a.txt'))

        redo = self.revert(recovery)
        self.assertEqual(redo['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), contents)

    def test_delete_then_create_keeps_original_and_final_states(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run(bundle(
            'DELETE a.txt',
            '',
            'WRITE a.txt',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ))
        recovery = self.revert(original)
        self.assertEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original\n')

    def test_old_manifest_without_existence_metadata_is_refused(self):
        import json
        self.put('a.txt', 'original\n')
        original = self.applied_run(
            replace_text('a.txt', 'original', 'edited')
        )
        path = os.path.join(original['artifact_dir'], 'manifest.json')
        with open(path, 'r', encoding='utf-8') as handle:
            manifest = json.load(handle)
        del manifest['touched'][0]['existed_after']
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(manifest, handle)

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'edited\n')
        self.assertIn(
            'Existence metadata missing',
            recovery['results'][0]['message'],
        )

    def test_symlink_substitution_is_refused(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run(
            replace_text('a.txt', 'original', 'edited')
        )
        self.put('elsewhere.txt', 'edited\n')
        path = os.path.join(self.project_root, 'a.txt')
        os.remove(path)
        try:
            os.symlink('elsewhere.txt', path)
        except (OSError, NotImplementedError) as error:
            self.skipTest('Host does not permit symlinks: %s' % error)

        recovery = self.revert(original)
        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertTrue(os.path.islink(path))
        self.assertEqual(self.get('elsewhere.txt'), 'edited\n')

    def test_failed_second_install_preserves_file_and_tracks_first(self):
        from unittest.mock import patch
        from forge.core import recovery as recovery_module

        self.put('a.txt', 'original a\n')
        self.put('b.txt', 'original b\n')
        original = self.applied_run(
            replace_text('a.txt', 'original a', 'edited a')
            + '\n\n'
            + replace_text('b.txt', 'original b', 'edited b')
        )
        second = os.path.join(self.project_root, 'b.txt')
        real_replace = os.replace

        def fail_second(source, destination):
            if destination == second:
                raise OSError('Injected atomic-install failure')
            return real_replace(source, destination)

        with patch.object(recovery_module.os, 'replace', fail_second):
            recovery = self.revert(original)

        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original a\n')
        self.assertEqual(self.get('b.txt'), 'edited b\n')
        self.assertEqual(
            [item['rel'] for item in recovery['touched_files']],
            ['a.txt'],
        )
        self.assertFalse(any(
            name.startswith('.forge-revert-')
            for name in os.listdir(self.project_root)
        ))

        undo_partial = self.revert(recovery)
        self.assertEqual(undo_partial['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'edited a\n')
        self.assertEqual(self.get('b.txt'), 'edited b\n')

    def test_change_during_recovery_is_preserved(self):
        from unittest.mock import patch
        from forge.core import recovery as recovery_module

        self.put('a.txt', 'original a\n')
        self.put('b.txt', 'original b\n')
        original = self.applied_run(
            replace_text('a.txt', 'original a', 'edited a')
            + '\n\n'
            + replace_text('b.txt', 'original b', 'edited b')
        )
        first = os.path.join(self.project_root, 'a.txt')
        real_replace = os.replace

        def replace_then_change_next(source, destination):
            answer = real_replace(source, destination)
            if destination == first:
                self.put('b.txt', 'arrived during recovery\n')
            return answer

        with patch.object(
            recovery_module.os, 'replace', replace_then_change_next,
        ):
            recovery = self.revert(original)

        self.assertNotEqual(recovery['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original a\n')
        self.assertEqual(self.get('b.txt'), 'arrived during recovery\n')
        self.assertEqual(
            [item['rel'] for item in recovery['touched_files']],
            ['a.txt'],
        )

    def test_repeating_recovery_refuses_without_changing_files(self):
        self.put('a.txt', 'original\n')
        original = self.applied_run(
            replace_text('a.txt', 'original', 'edited')
        )
        self.assertEqual(self.revert(original)['status'], 'APPLIED')
        repeated = self.revert(original)
        self.assertNotEqual(repeated['status'], 'APPLIED')
        self.assertEqual(self.get('a.txt'), 'original\n')
        self.assertFalse(repeated.get('touched_files'))


if __name__ == '__main__':
    unittest.main(verbosity=2)