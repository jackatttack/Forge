# -*- coding: utf-8 -*-
"""Recovery of content-aware records alongside legacy text recovery."""

import os
import stat

from .content_records import content_change
from .file_content import (
    atomic_install, file_signature, text_content, verify_content,
)


def _refuse(message):
    from .recovery import RecoveryRefused
    raise RecoveryRefused(message)


def _content(run_directory, item, side):
    """Resolve only root-contained, verified snapshot references."""
    from .recovery import _safe_path

    stored = item.get(side + '_content')
    if not isinstance(stored, dict):
        _refuse('Missing content description: ' + side)
    content = dict(stored)
    if content.get('encoding') == 'blob':
        content['path'] = _safe_path(
            run_directory, content.get('snapshot_rel'),
        )
    try:
        verify_content(content)
    except (ValueError, OSError) as error:
        _refuse('Invalid %s snapshot: %s' % (side, error))
    if item.get(side + '_sha') != content['sha256']:
        _refuse('Checksum metadata mismatch: ' + side)
    return content


def disk_state(root, relative):
    """Read byte identity and filesystem identity without buffering a file."""
    from .recovery import _safe_path

    path = _safe_path(root, relative)
    try:
        information = os.lstat(path)
    except FileNotFoundError:
        empty = text_content('')
        return path, False, 0, empty['sha256'], None
    if not stat.S_ISREG(information.st_mode):
        _refuse('Expected an ordinary file: ' + relative)
    size, checksum = file_signature(path)
    final = os.lstat(path)

    def identity(value):
        return (
            value.st_dev, value.st_ino, value.st_mode, value.st_size,
            getattr(value, 'st_mtime_ns', value.st_mtime),
        )

    if identity(information) != identity(final):
        _refuse('Target changed during inspection: ' + relative)
    return path, True, size, checksum, identity(final)


def prepare_entry(entry_root, run_directory, item):
    """Validate both stored endpoints and current disk state before recovery."""
    relative = item.get('rel')
    existed_before = item.get('existed_before')
    existed_after = item.get('existed_after')
    if type(existed_before) is not bool or type(existed_after) is not bool:
        _refuse('Existence metadata missing for ' + str(relative))

    before = _content(run_directory, item, 'before')
    after = _content(run_directory, item, 'after')
    if not existed_before and before['size']:
        _refuse('Absent original has contents: ' + relative)
    if not existed_after and after['size']:
        _refuse('Absent file has recorded contents: ' + relative)

    current = disk_state(entry_root, relative)
    if (
        current[1] != existed_after
        or (current[1] and current[2:4] != (after['size'], after['sha256']))
    ):
        _refuse('Current file has drifted: ' + relative)
    return {
        'content_record': True,
        'relative': relative,
        'root': entry_root,
        'root_name': item.get('root') or '',
        'current': current,
        'restore_exists': existed_before,
        'restore_content': before,
        'current_content': after,
    }


def install_entry(entry):
    """Atomically restore one state, recording the displaced exact contents."""
    root = entry['root']
    relative = entry['relative']
    current = entry['current']
    path, exists = current[:2]
    desired_exists = entry['restore_exists']
    desired = entry['restore_content']

    def recheck():
        if disk_state(root, relative) != current:
            _refuse('Target changed during recovery: ' + relative)

    if (
        exists == desired_exists
        and current[2:4] == (desired['size'], desired['sha256'])
    ):
        recheck()
        return None

    if desired_exists:
        atomic_install(path, desired, before_replace=recheck)
    else:
        recheck()
        os.remove(path)

    return content_change(
        relative, entry['current_content'], desired,
        existed_before=exists, existed_after=desired_exists,
        root=entry['root_name'],
    )