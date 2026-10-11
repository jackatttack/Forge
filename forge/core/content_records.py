# -*- coding: utf-8 -*-
"""Shared change aggregation and persistence of byte-exact content records."""

import os

from .file_content import (
    atomic_install, matches_file, text_content, verify_content,
)


def run_content_store(run):
    """Lazily own transfer snapshots for the lifetime of a run.

    Stored runs release temporary files after persistence. For store=False,
    the returned run owns them until release_content_store(run) or collection.
    """
    from .file_content import ContentStore
    store = run.get('_content_store')
    if store is None:
        store = ContentStore()
        run['_content_store'] = store
    return store


def release_content_store(run):
    """Release temporary snapshots after persistence or an unstored run."""
    store = run.pop('_content_store', None)
    if store is not None:
        store.close()


def content_change(
    relative, before, after, existed_before=True, existed_after=True, root='',
):
    """Describe a completed change without embedding binary data in JSON."""
    return {
        'rel': relative,
        'root': root or '',
        'kind': 'file',
        'existed_before': bool(existed_before),
        'existed_after': bool(existed_after),
        'before': before.get('text', ''),
        'after': after.get('text', ''),
        'before_content': before,
        'after_content': after,
    }


def state_content(item, side):
    """Adapt a legacy text state or return an explicit content description."""
    content = item.get(side + '_content')
    if content is not None:
        if not isinstance(content, dict):
            raise ValueError('Invalid %s content description' % side)
        return content
    text = item.get(side)
    return text_content('' if text is None else text)


def collect_changes(run):
    """Keep first-before/final-after states, keyed by root and relative path.

    Run-level records are authoritative and chronological. Operation records
    only supplement paths not present in the run-level list.
    """
    items = [
        item for item in (run or {}).get('touched_files') or []
        if isinstance(item, dict)
    ]

    def identity(item):
        relative = str(item.get('rel') or item.get('file') or '').strip()
        return (
            str(item.get('root') or ''),
            os.path.normpath(relative) if relative else '',
        )

    run_paths = {identity(item) for item in items}
    for result in (run or {}).get('results') or []:
        for item in result.get('touched') or []:
            if isinstance(item, dict) and identity(item) not in run_paths:
                items.append(item)

    combined = {}
    order = []
    for item in items:
        key = identity(item)
        root, relative = key
        if not relative:
            continue
        if key not in combined:
            order.append(key)
            combined[key] = dict(item)
            combined[key].update({'root': root, 'rel': relative})
            continue

        entry = combined[key]
        has_content = (
            'before_content' in entry or 'after_content' in entry
            or 'before_content' in item or 'after_content' in item
        )
        if has_content:
            entry['before_content'] = state_content(entry, 'before')
            entry['after_content'] = state_content(item, 'after')
        entry['after'] = item.get('after') or ''
        entry['existed_after'] = item.get('existed_after')
        entry['kind'] = item.get('kind') or entry.get('kind') or 'file'

    for entry in combined.values():
        for side in ('before', 'after'):
            content = state_content(entry, side)
            entry[side + '_sha'] = content['sha256']
    return [combined[key] for key in order]


def persist_run_contents(run, run_directory):
    """Save every referenced blob, including intermediate operation states.

    References are updated only after their verified snapshot is installed.
    Content-addressed names avoid duplicate payloads within this run.
    Text descriptions remain inline. No arbitrary bytes enter JSON.
    """
    visited = set()

    def visit(value):
        if not isinstance(value, (dict, list, tuple)):
            return
        identity = id(value)
        if identity in visited:
            return
        visited.add(identity)

        if isinstance(value, dict):
            if value.get('encoding') == 'blob' and 'sha256' in value:
                verify_content(value)
                checksum = value['sha256']
                if (
                    len(checksum) != 64
                    or any(character not in '0123456789abcdef' for character in checksum)
                ):
                    raise ValueError('Invalid snapshot checksum')
                relative = 'snapshots/blobs/' + checksum
                destination = os.path.join(run_directory, *relative.split('/'))
                if os.path.lexists(destination):
                    if not matches_file(destination, value):
                        raise ValueError('Stored snapshot checksum mismatch')
                else:
                    atomic_install(destination, value)
                value['path'] = destination
                value['snapshot_rel'] = relative
                return
            for child in list(value.values()):
                visit(child)
        else:
            for child in value:
                visit(child)

    # Only mutation records own payloads. Read-only result data may contain
    # historical manifest descriptions (for example DIFF <stamp>); those
    # references belong to the historical run and must not be re-imported.
    visit(run.get('touched_files') or [])
    for result in run.get('results') or []:
        visit(result.get('touched') or [])


def manifest_content(content):
    """Make a portable content description without an absolute snapshot path."""
    if content.get('encoding') == 'utf-8':
        verify_content(content)
        return {
            'encoding': 'utf-8',
            'text': content['text'],
            'size': content['size'],
            'sha256': content['sha256'],
        }
    if content.get('encoding') != 'blob' or not content.get('snapshot_rel'):
        raise ValueError('Binary snapshot has not been persisted')
    return {
        'encoding': 'blob',
        'snapshot_rel': content['snapshot_rel'],
        'size': content['size'],
        'sha256': content['sha256'],
    }


def manifest_change(item):
    """Serialize a content-aware change, retaining familiar summary fields."""
    before = manifest_content(state_content(item, 'before'))
    after = manifest_content(state_content(item, 'after'))
    return {
        'rel': item['rel'],
        'root': item.get('root') or '',
        'kind': 'file',
        'existed_before': item.get('existed_before'),
        'existed_after': item.get('existed_after'),
        'before': before.get('text', ''),
        'after': after.get('text', ''),
        'before_sha': before['sha256'],
        'after_sha': after['sha256'],
        'before_content': before,
        'after_content': after,
        'snapshot_rel': before.get('snapshot_rel', ''),
    }