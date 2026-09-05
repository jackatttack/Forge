# -*- coding: utf-8 -*-
"""Conflict-aware recovery of recorded UTF-8 text-file changes.

Validate every target and snapshot before mutation. Recheck each target
immediately before installation, then report each completed change.

This is not a multi-file transaction or a lock against concurrent writers.
Completed-change records still rely on the caller's normal run persistence.
"""

import hashlib
import os
import stat
import tempfile

from .file_safety import touched_file


class RecoveryRefused(ValueError):
    """Recovery evidence is incomplete, invalid, or no longer applicable."""


def _digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _safe_path(root, relative):
    """Reject escaping paths and symlink components, including dangling links."""
    if not isinstance(relative, str) or not relative:
        raise RecoveryRefused('Missing relative file path')
    if os.path.isabs(relative) or '..' in relative.split(os.sep):
        raise RecoveryRefused('Unsafe relative path: ' + relative)

    root = os.path.realpath(root)
    path = os.path.abspath(os.path.join(root, relative))
    if path == root or not path.startswith(root + os.sep):
        raise RecoveryRefused('Path escapes its root: ' + relative)

    cursor = root
    for part in os.path.relpath(path, root).split(os.sep):
        cursor = os.path.join(cursor, part)
        if os.path.islink(cursor):
            raise RecoveryRefused('Symlink path refused: ' + relative)
    return path


def _state(root, relative):
    """Read exact UTF-8 contents and a file identity for change detection."""
    path = _safe_path(root, relative)
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        if not os.path.isdir(os.path.dirname(path)):
            raise RecoveryRefused('Parent directory is missing: ' + relative)
        return path, False, '', None

    if not stat.S_ISREG(information.st_mode):
        raise RecoveryRefused('Expected an ordinary file: ' + relative)

    with open(path, 'rb') as handle:
        text = handle.read().decode('utf-8')

    identity = (
        information.st_dev,
        information.st_ino,
        information.st_mode,
        information.st_size,
        getattr(information, 'st_mtime_ns', information.st_mtime),
    )
    return path, True, text, identity


def _verified_text(text, expected_hash, label):
    if not isinstance(text, str) or not isinstance(expected_hash, str):
        raise RecoveryRefused('Missing text or checksum: ' + label)
    if _digest(text) != expected_hash:
        raise RecoveryRefused('Checksum mismatch: ' + label)
    return text


def _prepare(project_root, run_directory, manifest):
    """Build the complete recovery plan without changing project files."""
    if not isinstance(manifest, dict):
        raise RecoveryRefused('Manifest must be an object')
    recorded_root = manifest.get('root')
    if not isinstance(recorded_root, str) or (
        os.path.realpath(recorded_root) != os.path.realpath(project_root)
    ):
        raise RecoveryRefused('Manifest belongs to a different project')

    touched = manifest.get('touched')
    if not isinstance(touched, list):
        raise RecoveryRefused('Manifest has no valid touched-file list')

    plan = []
    seen = set()
    for item in touched:
        if not isinstance(item, dict) or item.get('kind') != 'file':
            raise RecoveryRefused('Only recorded ordinary files can be recovered')

        relative = item.get('rel')
        current = _state(project_root, relative)
        path, exists, text, identity = current
        if path in seen:
            raise RecoveryRefused('Duplicate recovery target: ' + relative)
        seen.add(path)

        existed_before = item.get('existed_before')
        existed_after = item.get('existed_after')
        if type(existed_before) is not bool or type(existed_after) is not bool:
            raise RecoveryRefused(
                'Existence metadata missing for %s; inspect this older or '
                'incomplete record and recover manually' % relative
            )

        after = _verified_text(
            item.get('after'), item.get('after_sha'), relative + ' after',
        )
        if not existed_after and after:
            raise RecoveryRefused('Absent file has recorded contents: ' + relative)

        if exists != existed_after or (exists and text != after):
            raise RecoveryRefused('Current file has drifted: ' + relative)

        if existed_before and item.get('snapshot_rel'):
            snapshot = _state(run_directory, item['snapshot_rel'])
            if not snapshot[1]:
                raise RecoveryRefused('Snapshot is missing: ' + relative)
            before = snapshot[2]
        else:
            before = item.get('before')

        before = _verified_text(
            before, item.get('before_sha'), relative + ' before',
        )
        if not existed_before and before:
            raise RecoveryRefused('Absent original has contents: ' + relative)

        plan.append({
            'relative': relative,
            'current': current,
            'restore_exists': existed_before,
            'restore_text': before,
        })
    return plan


def _recheck(project_root, entry):
    current = _state(project_root, entry['relative'])
    if current != entry['current']:
        raise RecoveryRefused(
            'Target changed during recovery: ' + entry['relative']
        )


def _install(project_root, entry):
    """Install one recovery step without truncating an existing destination."""
    path, exists, text, identity = entry['current']
    desired_exists = entry['restore_exists']
    desired_text = entry['restore_text']

    if exists == desired_exists and text == desired_text:
        _recheck(project_root, entry)
        return None

    if desired_exists:
        descriptor, staged = tempfile.mkstemp(
            prefix='.forge-revert-', dir=os.path.dirname(path),
        )
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(desired_text.encode('utf-8'))
                handle.flush()
                os.fsync(handle.fileno())
            if exists:
                os.chmod(staged, stat.S_IMODE(identity[2]))
            _recheck(project_root, entry)
            os.replace(staged, path)
        finally:
            if os.path.exists(staged):
                os.remove(staged)
    else:
        _recheck(project_root, entry)
        # Only an ordinary file can reach this point. Never recurse.
        os.remove(path)

    return touched_file(
        entry['relative'],
        text,
        desired_text,
        existed_before=exists,
        existed_after=desired_exists,
    )


def restore_manifest(
    project_root, run_directory, manifest, on_change=None, report=None,
):
    """Return (success, message), reporting completed changes even on failure."""
    if report is None:
        report = {}
    report.update({
        'status': 'UNKNOWN',
        'restored': 0,
        'deleted': 0,
        'unchanged': 0,
        'changes': [],
    })

    try:
        plan = _prepare(project_root, run_directory, manifest)
    except (RecoveryRefused, OSError, UnicodeError) as error:
        report['status'] = 'FAILED_RECOVERY'
        return False, 'Recovery refused before mutation: ' + str(error)

    for entry in plan:
        try:
            change = _install(project_root, entry)
            if change is None:
                report['unchanged'] += 1
                continue
            report['changes'].append(change)
            counter = 'restored' if change['existed_after'] else 'deleted'
            report[counter] += 1
            if on_change is not None:
                on_change(change)
        except (RecoveryRefused, OSError, UnicodeError) as error:
            report['status'] = 'FAILED_RECOVERY'
            return False, (
                'Recovery stopped after %d completed change(s): %s. '
                'Inspect the recorded partial recovery.'
                % (len(report['changes']), error)
            )

    report['status'] = 'APPLIED'
    return True, (
        'Recovery complete (restored %d, deleted %d, unchanged %d).'
        % (report['restored'], report['deleted'], report['unchanged'])
    )