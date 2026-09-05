# -*- coding: utf-8 -*-
"""
Durable run storage for the Forge.

Stores:
- source bundle
- LLM packet
- Surface output
- structured run JSON
- recovery manifest
- before snapshots for touched files

Important recovery rule:
If a file did not exist before the run, REVERT_RUN deletes it.
"""

import json
import os
import shutil

# Pythonista does not support rmdir(dir_fd=...), despite shutil selecting
# its descriptor-based rmtree implementation. Forge only prunes its own
# resolved artifact directories, so use shutil's portable path fallback.
if hasattr(shutil, "_use_fd_functions"):
    shutil._use_fd_functions = False
import hashlib
from datetime import datetime


def now_stamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def allocate_stamp(
    project_root,
    mode='dev',
    environment=None,
):
    """
    Return a run stamp that will not overwrite an existing run directory.

    Storage remains mode-scoped so dev, test and ephemeral histories are
    independent.
    """
    base = now_stamp()

    root = runs_root(
        project_root,
        mode=mode,
        environment=environment,
    )

    first = os.path.join(
        root,
        base,
    )

    if not os.path.exists(first):
        return base

    for i in range(2, 1000):
        candidate = '%s_%02d' % (
            base,
            i,
        )

        if not os.path.exists(
            os.path.join(
                root,
                candidate,
            )
        ):
            return candidate

    return (
        base
        + '_'
        + datetime.now().strftime('%f')
    )


def _is_forge_home(path):
    path = os.path.abspath(str(path or ''))
    return (
        os.path.isfile(os.path.join(path, 'entry.py'))
        and os.path.isdir(os.path.join(path, 'forge_core'))
        and os.path.isdir(os.path.join(path, 'forge_packages'))
    )


def _find_forge_home_from_path(path):
    """
    Compatibility helper for an explicitly supplied path.

    No cwd, environment variable, or host discovery is performed.
    """
    value = str(
        path
        or ''
    ).strip()

    if not value:
        return ''

    cur = os.path.abspath(
        value
    )

    if os.path.isfile(
        cur
    ):
        cur = os.path.dirname(
            cur
        )

    for _ in range(12):
        if _is_forge_home(
            cur
        ):
            return cur

        parent = os.path.dirname(
            cur
        )

        if parent == cur:
            break

        cur = parent

    return ''


def forge_home(
    project_root=None,
    environment=None,
):
    """
    Compatibility accessor for an explicitly supplied Forge home.

    Portable storage no longer discovers Forge home from cwd or FORGE_HOME.
    """
    environment = (
        environment
        or {}
    )

    explicit = str(
        environment.get(
            'forge_home'
        )
        or ''
    ).strip()

    if explicit:
        return os.path.abspath(
            explicit
        )

    candidate = str(
        project_root
        or ''
    ).strip()

    if (
        candidate
        and _is_forge_home(
            candidate
        )
    ):
        return os.path.abspath(
            candidate
        )

    raise ValueError(
        'Forge home must be supplied explicitly.'
    )


def artifacts_root(
    project_root=None,
    environment=None,
    storage_root=None,
):
    """
    Return the explicit Forge-owned artifact root.

    Portable Forge never infers storage from project_root, cwd, FORGE_HOME,
    or an installation search.
    """
    if storage_root:
        return os.path.abspath(
            str(
                storage_root
            )
        )

    environment = (
        environment
        or {}
    )

    explicit = str(
        environment.get(
            'storage_root'
        )
        or ''
    ).strip()

    if explicit:
        return os.path.abspath(
            explicit
        )

    raise ValueError(
        'Forge storage requires explicit storage_root.'
    )


def _storage_mode(mode):
    mode = str(mode or 'dev').strip().lower()
    if mode in ('test', 'tests'):
        return 'test'
    if mode in ('ephemeral', 'temp', 'tmp'):
        return 'ephemeral'
    return 'dev'


def runs_root(
    project_root=None,
    mode='dev',
    environment=None,
    storage_root=None,
):
    """Return the artifact root for one bounded run-storage lane."""
    mode = _storage_mode(mode)

    root = artifacts_root(
        project_root,
        environment=environment,
        storage_root=storage_root,
    )

    if mode == 'test':
        return os.path.join(
            root,
            'test_runs',
        )

    if mode == 'ephemeral':
        return os.path.join(
            root,
            'runs_ephemeral',
        )

    return os.path.join(
        root,
        'runs',
    )


def _candidate_run_roots(
    project_root,
    mode='dev',
    environment=None,
):
    """Roots to search when reading an existing run stamp."""
    modes = [
        _storage_mode(mode),
        'dev',
        'test',
        'ephemeral',
    ]

    out = []
    seen = set()

    for item in modes:
        root = runs_root(
            project_root,
            mode=item,
            environment=environment,
        )

        if root not in seen:
            seen.add(root)
            out.append(root)

    return out


def _run_dir(
    project_root,
    stamp,
    mode='dev',
    environment=None,
):
    stamp = str(
        stamp
        or ''
    ).strip()

    if not stamp:
        return ''

    for root in _candidate_run_roots(
        project_root,
        mode=mode,
        environment=environment,
    ):
        path = os.path.join(
            root,
            stamp,
        )

        if os.path.isdir(path):
            return path

    return os.path.join(
        runs_root(
            project_root,
            mode=mode,
            environment=environment,
        ),
        stamp,
    )


def _ensure(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _write(path, text):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def _read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def _sha(text):
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def _json_safe(obj, _seen=None):
    """Return a JSON-serialisable copy of obj.

    Run objects can contain convenience references back to themselves, especially
    through Surface/detail page data. json.dumps raises ValueError on circular
    references, so this helper must break cycles before storage.
    """
    if _seen is None:
        _seen = set()

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    obj_id = id(obj)
    if obj_id in _seen:
        return '<circular>'

    if isinstance(obj, dict):
        _seen.add(obj_id)
        out = {}
        for key, value in obj.items():
            safe_key = key
            if not isinstance(safe_key, str):
                safe_key = str(safe_key)
            out[safe_key] = _json_safe(value, _seen)
        _seen.discard(obj_id)
        return out

    if isinstance(obj, (list, tuple)):
        _seen.add(obj_id)
        out = [_json_safe(item, _seen) for item in obj]
        _seen.discard(obj_id)
        return out

    if isinstance(obj, set):
        _seen.add(obj_id)
        out = [_json_safe(item, _seen) for item in sorted(obj, key=lambda x: str(x))]
        _seen.discard(obj_id)
        return out

    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)


def _collect_touched(run):
    """Keep each path's initial state and its final recorded state.

    The run-level list is chronological and authoritative. Result-only
    records supplement paths absent from it, without replaying the duplicate
    records normally present on both the run and its operation results.
    """
    items = [
        dict(item) for item in run.get('touched_files') or []
        if isinstance(item, dict)
    ]

    def relative_path(item):
        value = str(item.get('rel') or item.get('file') or '').strip()
        return os.path.normpath(value) if value else ''

    run_paths = {relative_path(item) for item in items}
    for result in run.get('results') or []:
        for item in result.get('touched') or []:
            if isinstance(item, dict) and relative_path(item) not in run_paths:
                items.append(dict(item))

    combined = {}
    order = []
    for item in items:
        rel = relative_path(item)
        if not rel:
            continue
        if rel not in combined:
            order.append(rel)
            combined[rel] = {
                'rel': rel,
                'kind': item.get('kind') or 'file',
                'existed_before': bool(item.get('existed_before')),
                'before': item.get('before') or '',
            }

        entry = combined[rel]
        entry['after'] = item.get('after') or ''
        # Missing metadata stays unknown; do not guess absence from "".
        entry['existed_after'] = item.get('existed_after')
        entry['before_sha'] = _sha(entry['before'])
        entry['after_sha'] = _sha(entry['after'])

    return [combined[rel] for rel in order]

MAX_STORED_RUNS = 100


def retention_limit(environment=None):
    """Return the resolved per-lane run retention limit."""
    storage = (
        (environment or {}).get(
            'storage'
        )
        or {}
    )

    value = storage.get(
        'max_runs',
        MAX_STORED_RUNS,
    )

    try:
        value = int(
            value
        )
    except Exception:
        return MAX_STORED_RUNS

    if value < 1:
        return MAX_STORED_RUNS

    return value

def prune_runs(
    project_root,
    keep=None,
    mode='dev',
    environment=None,
):
    """
    Delete old run directories in one storage lane.

    Behaviour:
    - newest run directories are retained
    - each lane is bounded independently
    - deletion failures are non-fatal
    - explicit keep overrides configuration
    - otherwise environment storage.max_runs is used
    - portable default remains 100
    """
    if keep is None:
        keep = retention_limit(
            environment
        )

    root = runs_root(
        project_root,
        mode=mode,
        environment=environment,
    )

    if not os.path.isdir(root):
        return []

    try:
        names = [
            name
            for name in os.listdir(root)
            if os.path.isdir(
                os.path.join(
                    root,
                    name,
                )
            )
        ]
    except OSError:
        return []

    names.sort(
        reverse=True
    )

    stale = names[
        int(keep):
    ]

    removed = []

    for name in stale:
        path = os.path.join(
            root,
            name,
        )

        try:
            shutil.rmtree(
                path
            )
            removed.append(
                name
            )
        except OSError:
            pass

    return removed

def write_run(run, environment=None):
    environment = (
        environment
        or (run or {}).get('environment')
        or {}
    )

    project_root = str(
        environment.get('project_root')
        or (run or {}).get('project_root')
        or ''
    ).strip()

    if not project_root:
        raise ValueError(
            'Run storage requires an explicit project_root.'
        )

    project_root = os.path.abspath(
        project_root
    )

    mode = _storage_mode(
        run.get('mode')
        or 'dev'
    )

    stamp = (
        run.get('stamp')
        or now_stamp()
    )

    run['stamp'] = stamp
    run['mode'] = mode

    root = os.path.join(
        runs_root(
            project_root,
            mode=mode,
            environment=environment,
        ),
        stamp,
    )

    snap_dir = os.path.join(
        root,
        'snapshots',
    )

    _ensure(root)
    _ensure(snap_dir)

    touched = _collect_touched(
        run
    )

    manifest_touched = []

    for item in touched:
        rel = item.get('rel') or ''
        snapshot_rel = ''

        if item.get('existed_before'):
            snapshot_rel = os.path.join(
                'snapshots',
                rel,
            )

            _write(
                os.path.join(
                    root,
                    snapshot_rel,
                ),
                item.get('before')
                or '',
            )

        manifest_touched.append({
            'rel': rel,
            'kind': item.get('kind') or 'file',
            'existed_before': bool(
                item.get('existed_before')
            ),
            'snapshot_rel': snapshot_rel,
            'existed_after': item.get('existed_after'),
            'before_sha': (
                item.get('before_sha')
                or _sha(
                    item.get('before')
                    or ''
                )
            ),
            'after_sha': (
                item.get('after_sha')
                or _sha(
                    item.get('after')
                    or ''
                )
            ),
            'before': (
                item.get('before')
                or ''
            ),
            'after': (
                item.get('after')
                or ''
            ),
        })

    manifest = {
        'stamp': stamp,
        'mode': mode,
        'root': project_root,
        'status': (
            run.get('status')
            or 'UNKNOWN'
        ),
        'touched': manifest_touched,
    }

    run['touched_files'] = (
        manifest_touched
    )

    _write(
        os.path.join(
            root,
            'bundle.txt',
        ),
        run.get('input_bundle')
        or '',
    )

    _write(
        os.path.join(
            root,
            'packet.txt',
        ),
        run.get('packet')
        or '',
    )

    # Compatibility artifact while Surface migration is in progress.
    _write(
        os.path.join(
            root,
            'surface.txt',
        ),
        run.get('surface_text')
        or '',
    )

    _write(
        os.path.join(
            root,
            'manifest.json',
        ),
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + '\n',
    )

    safe = _json_safe(
        run
    )

    _write(
        os.path.join(
            root,
            'run.json',
        ),
        json.dumps(
            safe,
            indent=2,
            sort_keys=True,
        )
        + '\n',
    )

    # Critical Forge behaviour:
    # every completed write automatically bounds its own storage lane.
    prune_runs(
        project_root,
        mode=mode,
        environment=environment,
    )

    return root


def list_runs(
    project_root,
    limit=20,
    mode='dev',
    environment=None,
):
    root = runs_root(
        project_root,
        mode=mode,
        environment=environment,
    )

    if not os.path.isdir(root):
        return []

    names = [
        name
        for name in os.listdir(root)
        if os.path.isdir(
            os.path.join(
                root,
                name,
            )
        )
    ]

    names.sort(
        reverse=True
    )

    return names[:limit]


def read_text(
    project_root,
    stamp,
    name,
    mode='dev',
    environment=None,
):
    run_dir = _run_dir(
        project_root,
        stamp,
        mode=mode,
        environment=environment,
    )

    path = os.path.join(
        run_dir,
        name,
    )

    if not os.path.isfile(path):
        return None

    return _read(path)


def read_manifest(
    project_root,
    stamp,
    mode='dev',
    environment=None,
):
    run_dir = _run_dir(
        project_root,
        stamp,
        mode=mode,
        environment=environment,
    )

    path = os.path.join(
        run_dir,
        'manifest.json',
    )

    if not os.path.isfile(path):
        return (
            None,
            'Manifest not found for run: '
            + str(stamp),
        )

    try:
        return (
            json.loads(
                _read(path)
            ),
            None,
        )
    except Exception as e:
        return (
            None,
            'Manifest unreadable: %s: %s'
            % (
                type(e).__name__,
                e,
            ),
        )


def revert_run(
    project_root, stamp, mode='dev', environment=None,
    on_change=None, report=None,
):
    """Recover a stored run only when all recorded states still match.

    The optional callback receives each completed file change. The report
    exposes partial completion without changing the historical tuple return.
    """
    from .recovery import restore_manifest

    manifest, error = read_manifest(
        project_root, stamp, mode=mode, environment=environment,
    )
    if error:
        if report is not None:
            report['status'] = 'FAILED_RECOVERY'
        return False, error

    return restore_manifest(
        project_root,
        _run_dir(
            project_root, stamp, mode=mode, environment=environment,
        ),
        manifest,
        on_change=on_change,
        report=report,
    )
