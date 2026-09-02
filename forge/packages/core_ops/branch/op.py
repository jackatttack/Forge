# -*- coding: utf-8 -*-
"""
BRANCH reboot op.

Named filesystem checkpoints for the Forge.

This is deliberately close to current Forge behaviour:
- BRANCH create <name> snapshots listed paths
- BRANCH restore <name> restores captured files
- BRANCH list shows saved branches
- BRANCH delete <name> removes a saved branch
- create writes a standalone restore_branch.py for disaster recovery
"""

import json
import os
import shutil
import time


SPEC = {
    'name': 'BRANCH',
    'target_kind': 'none',
    'body_mode': 'optional',
    'allowed_directives': set(['ARGS', 'CONFIRM']),
    'required_directives': set(),
}

HELP = {
    'summary': 'Create, restore, list, or delete named filesystem checkpoints.',
    'minimal_example': [
        'BRANCH create before_big_change',
        'BEGIN_BODY',
        'forge/',
        'END_BODY',
        '',
        'BRANCH restore before_big_change',
        '',
        'BRANCH list',
        '',
        'BRANCH delete before_big_change',
    ],
}


DEFAULT_KEEP_BRANCHES = 100


HINTS = {
    '_max_hints': 1,
    'subcommand': {
        'message': 'BRANCH needs a subcommand.',
        'why': 'Branches create, restore, list, or delete named filesystem checkpoints.',
        'example': [
            'BRANCH create before_change',
            'BEGIN_BODY',
            'forge/smoke.py',
            'END_BODY',
            '',
            'BRANCH list',
        ],
        'next': [
            'Use create, restore, list, or delete.',
            'Include paths in the body when creating a branch.',
        ],
    },
    'restore': {
        'message': 'Branch restore needs an existing branch name.',
        'why': 'Forge cannot restore a checkpoint unless that branch exists on disk.',
        'example': [
            'BRANCH list',
            '',
            'BRANCH restore before_change',
        ],
        'next': [
            'Run BRANCH list.',
            'Copy the branch name exactly.',
        ],
    },
}

def validate(parsed_op):
    args = ((parsed_op.get('directives') or {}).get('ARGS') or parsed_op.get('target') or '').strip()
    if not args:
        return ['BRANCH requires a subcommand: create <name>, restore <name>, delete <name>, or list']

    parts = args.split(None, 1)
    sub = parts[0]
    name = parts[1].strip() if len(parts) > 1 else ''

    if sub not in ('create', 'restore', 'list', 'delete'):
        return ['BRANCH unknown subcommand: ' + sub]

    if sub in ('create', 'restore', 'delete') and not name:
        return ['BRANCH %s requires a name' % sub]

    if sub == 'create' and not (parsed_op.get('body') or '').strip():
        return ['BRANCH create requires body paths']

    return []


def _project_root(ctx):
    from forge.core.environment import path_from_ctx

    return path_from_ctx(
        ctx,
        'project_root',
    )


def _storage_root(ctx):
    from forge.core.environment import path_from_ctx

    return path_from_ctx(
        ctx,
        'storage_root',
    )


def _branches_root(ctx):
    return os.path.join(
        _storage_root(ctx),
        'branches',
    )


def _branch_dir(ctx, name):
    return os.path.join(
        _branches_root(ctx),
        name,
    )


def _manifest_path(ctx, name):
    return os.path.join(
        _branch_dir(
            ctx,
            name,
        ),
        'manifest.json',
    )


def _ensure(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _in_root(root, path):
    root_real = os.path.realpath(os.path.abspath(root))
    path_real = os.path.realpath(os.path.abspath(path))
    return path_real == root_real or path_real.startswith(root_real + os.sep)


def _branch_name_safe(name):
    clean = ''.join(ch if ch.isalnum() or ch in ('_', '-', '.') else '_' for ch in str(name or '').strip())
    return clean.strip('._') or 'branch'


def _read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def _write(path, text):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def _copy_file(src, dst):
    parent = os.path.dirname(dst)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.copy2(src, dst)


def _iter_snapshot_files(root, requested):
    files = []
    missing = []

    for raw in requested:
        rel = str(raw or '').strip()
        if not rel:
            continue

        abs_path = os.path.abspath(os.path.join(root, rel))
        if not _in_root(root, abs_path):
            missing.append(rel + ' (escapes project root)')
            continue

        if os.path.isfile(abs_path):
            files.append(os.path.relpath(abs_path, root))
            continue

        if os.path.isdir(abs_path):
            for dirpath, dirnames, filenames in os.walk(abs_path):
                dirnames[:] = sorted(
                    d for d in dirnames
                    if not d.startswith('.') and d != '__pycache__'
                )
                for fn in sorted(filenames):
                    if fn.startswith('.'):
                        continue
                    full = os.path.join(dirpath, fn)
                    files.append(os.path.relpath(full, root))
            continue

        # Missing snapshot targets are allowed during create flows.
        # This lets callers branch a package/file path before it exists.
        # Unsafe paths above still go into missing and remain hard failures.
        continue

    # Stable de-duplication.
    out = []
    seen = set()
    for rel in files:
        if rel not in seen:
            out.append(rel)
            seen.add(rel)
    return out, missing


def _write_restore_script(ctx, root, name):
    script = r'''# -*- coding: utf-8 -*-
"""
Standalone Forge branch restore script.

The project boundary is recorded in manifest.json when the branch is created.
No host, cwd, installation, or platform discovery is performed.
"""

import json
import os
import shutil


HERE = os.path.dirname(
    os.path.abspath(__file__)
)

MANIFEST = os.path.join(
    HERE,
    'manifest.json',
)


def _in_root(root, path):
    root_real = os.path.realpath(
        os.path.abspath(root)
    )

    path_real = os.path.realpath(
        os.path.abspath(path)
    )

    return (
        path_real == root_real
        or path_real.startswith(
            root_real + os.sep
        )
    )


def main():
    if not os.path.isfile(
        MANIFEST
    ):
        print(
            'ERROR: missing manifest.json'
        )
        return

    with open(
        MANIFEST,
        'r',
        encoding='utf-8',
    ) as f:
        manifest = json.load(
            f
        )

    root = str(
        manifest.get(
            'project_root'
        )
        or manifest.get(
            'root'
        )
        or ''
    ).strip()

    if not root:
        print(
            'ERROR: manifest has no project_root'
        )
        return

    root = os.path.abspath(
        root
    )

    restored = 0
    failed = []

    for rel in (
        manifest.get(
            'files'
        )
        or []
    ):
        src = os.path.join(
            HERE,
            'files',
            rel,
        )

        dst = os.path.abspath(
            os.path.join(
                root,
                rel,
            )
        )

        if not _in_root(
            root,
            dst,
        ):
            failed.append(
                rel
                + ': escapes project root'
            )
            continue

        if not os.path.isfile(
            src
        ):
            failed.append(
                rel
                + ' missing from branch'
            )
            continue

        try:
            parent = os.path.dirname(
                dst
            )

            if (
                parent
                and not os.path.isdir(
                    parent
                )
            ):
                os.makedirs(
                    parent
                )

            shutil.copy2(
                src,
                dst,
            )

            restored += 1

        except Exception as e:
            failed.append(
                rel
                + ': '
                + str(e)
            )

    print(
        'Restored %d file(s) from branch %s'
        % (
            restored,
            manifest.get(
                'name'
            )
            or '?',
        )
    )

    if failed:
        print(
            'Failures:'
        )

        for item in failed:
            print(
                '- ' + item
            )


if __name__ == '__main__':
    main()
'''

    _write(
        os.path.join(
            _branch_dir(
                ctx,
                name,
            ),
            'restore_branch.py',
        ),
        script,
    )


def _branch_entries(ctx):
    root = _project_root(
        ctx
    )

    base = _branches_root(
        ctx
    )

    if not os.path.isdir(
        base
    ):
        return []

    root_real = os.path.realpath(
        root
    )

    rows = []

    for name in os.listdir(
        base
    ):
        bdir = os.path.join(
            base,
            name,
        )

        mpath = os.path.join(
            bdir,
            'manifest.json',
        )

        if (
            not os.path.isdir(
                bdir
            )
            or not os.path.isfile(
                mpath
            )
        ):
            continue

        try:
            with open(
                mpath,
                'r',
                encoding='utf-8',
            ) as f:
                manifest = json.load(
                    f
                )
        except Exception:
            manifest = {}

        manifest_root = str(
            manifest.get(
                'project_root'
            )
            or manifest.get(
                'root'
            )
            or ''
        ).strip()

        # Branch listing/pruning is scoped to this resolved project.
        if (
            manifest_root
            and os.path.realpath(
                os.path.abspath(
                    manifest_root
                )
            ) != root_real
        ):
            continue

        rows.append({
            'name': name,
            'path': bdir,
            'project_root': (
                manifest_root
                or root
            ),
            'created': (
                manifest.get(
                    'created'
                )
                or ''
            ),
            'file_count': len(
                manifest.get(
                    'files'
                )
                or []
            ),
            'mtime': os.path.getmtime(
                mpath
            ),
        })

    rows.sort(
        key=lambda r: (
            r.get(
                'mtime'
            )
            or 0,
            r.get(
                'name'
            )
            or '',
        ),
        reverse=True,
    )

    return rows


def _prune(
    ctx,
    keep=DEFAULT_KEEP_BRANCHES,
    protect='',
):
    rows = _branch_entries(
        ctx
    )

    if len(
        rows
    ) <= keep:
        return []

    victims = [
        r
        for r in rows[
            keep:
        ]
        if r.get(
            'name'
        ) != protect
    ]

    pruned = []

    for row in victims:
        try:
            shutil.rmtree(
                row.get(
                    'path'
                )
            )

            pruned.append(
                row.get(
                    'name'
                )
            )

        except Exception:
            pass

    return pruned


def _create(ctx, result, name, body):
    root = _project_root(
        ctx
    )

    name = _branch_name_safe(
        name
    )

    requested = [
        line.strip()
        for line in str(
            body
            or ''
        ).splitlines()
        if line.strip()
    ]

    files, missing = _iter_snapshot_files(
        root,
        requested,
    )

    if missing:
        result['status'] = 'FAILED_IO'
        result['message'] = (
            'Branch create path problem: '
            + '; '.join(
                missing[:3]
            )
        )
        return

    bdir = _branch_dir(
        ctx,
        name,
    )

    if os.path.isdir(
        bdir
    ):
        shutil.rmtree(
            bdir
        )

    _ensure(
        os.path.join(
            bdir,
            'files',
        )
    )

    for rel in files:
        _copy_file(
            os.path.join(
                root,
                rel,
            ),
            os.path.join(
                bdir,
                'files',
                rel,
            ),
        )

    manifest = {
        'name': name,
        'created': time.strftime(
            '%Y-%m-%dT%H:%M:%S'
        ),
        'project_root': root,
        'requested': requested,
        'files': files,
    }

    _write(
        _manifest_path(
            ctx,
            name,
        ),
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + '\n',
    )

    _write_restore_script(
        ctx,
        root,
        name,
    )

    pruned = _prune(
        ctx,
        protect=name,
    )

    restore_path = os.path.join(
        _branch_dir(
            ctx,
            name,
        ),
        'restore_branch.py',
    )

    result['status'] = 'APPLIED'
    result['message'] = (
        "Branch '%s' created — %d file(s)"
        % (
            name,
            len(files),
        )
    )

    if pruned:
        result['message'] += (
            '; pruned %d old branch(es)'
            % len(
                pruned
            )
        )

    result['preview'] = (
        "BRANCH %s\nfiles: %d\nrestore: %s"
        % (
            name,
            len(files),
            restore_path,
        )
    )

    result['data'] = {
        'name': name,
        'files': len(
            files
        ),
        'pruned': pruned,
        'artifact_dir': bdir,
        'restore_script': restore_path,
    }


def _restore(ctx, result, name):
    root = _project_root(
        ctx
    )

    name = _branch_name_safe(
        name
    )

    mpath = _manifest_path(
        ctx,
        name,
    )

    if not os.path.isfile(
        mpath
    ):
        result['status'] = (
            'FAILED_NOT_FOUND'
        )
        result['message'] = (
            'Branch not found: '
            + name
        )
        return

    try:
        manifest = json.loads(
            _read(
                mpath
            )
        )
    except Exception as e:
        result['status'] = (
            'FAILED_IO'
        )
        result['message'] = (
            'Manifest unreadable: %s: %s'
            % (
                type(e).__name__,
                e,
            )
        )
        return

    manifest_root = str(
        manifest.get(
            'project_root'
        )
        or manifest.get(
            'root'
        )
        or ''
    ).strip()

    if (
        manifest_root
        and os.path.realpath(
            os.path.abspath(
                manifest_root
            )
        ) != os.path.realpath(
            root
        )
    ):
        result['status'] = (
            'FAILED_IO'
        )
        result['message'] = (
            'Branch belongs to a different project root.'
        )
        return

    restored = 0
    failed = []

    for rel in (
        manifest.get(
            'files'
        )
        or []
    ):
        src = os.path.join(
            _branch_dir(
                ctx,
                name,
            ),
            'files',
            rel,
        )

        dst = os.path.abspath(
            os.path.join(
                root,
                rel,
            )
        )

        if not _in_root(
            root,
            dst,
        ):
            failed.append(
                rel
                + ': escapes project root'
            )
            continue

        try:
            _copy_file(
                src,
                dst,
            )
            restored += 1
        except Exception as e:
            failed.append(
                rel
                + ': '
                + str(e)
            )

    if failed:
        result['status'] = (
            'FAILED_IO'
        )
        result['message'] = (
            'Branch restore had %d failure(s). Restored %d.'
            % (
                len(failed),
                restored,
            )
        )
        result['preview'] = (
            '\n'.join(
                failed[:10]
            )
        )
        return

    result['status'] = 'APPLIED'
    result['message'] = (
        "Branch '%s' restored — %d file(s)"
        % (
            name,
            restored,
        )
    )

    result['data'] = {
        'name': name,
        'restored': restored,
    }


def _list(ctx, result):
    rows = _branch_entries(
        ctx
    )

    lines = [
        'BRANCHES',
    ]

    if not rows:
        lines.append(
            '(none)'
        )
    else:
        for row in rows:
            lines.append(
                '- %s  %d file(s)'
                % (
                    row.get(
                        'name'
                    ),
                    row.get(
                        'file_count'
                    )
                    or 0,
                )
            )

    result['status'] = 'APPLIED'
    result['message'] = (
        '%d branch(es)'
        % len(rows)
    )
    result['preview'] = (
        '\n'.join(
            lines
        )
    )
    result['data'] = {
        'branches': rows,
    }


def _delete(ctx, result, name):
    name = _branch_name_safe(
        name
    )

    bdir = _branch_dir(
        ctx,
        name,
    )

    if not os.path.isdir(
        bdir
    ):
        result['status'] = (
            'FAILED_NOT_FOUND'
        )
        result['message'] = (
            'Branch not found: '
            + name
        )
        return

    # Refuse to delete a same-named branch belonging to another project.
    mpath = _manifest_path(
        ctx,
        name,
    )

    if os.path.isfile(
        mpath
    ):
        try:
            manifest = json.loads(
                _read(
                    mpath
                )
            )
        except Exception:
            manifest = {}

        manifest_root = str(
            manifest.get(
                'project_root'
            )
            or manifest.get(
                'root'
            )
            or ''
        ).strip()

        current_root = _project_root(
            ctx
        )

        if (
            manifest_root
            and os.path.realpath(
                os.path.abspath(
                    manifest_root
                )
            ) != os.path.realpath(
                current_root
            )
        ):
            result['status'] = (
                'FAILED_IO'
            )
            result['message'] = (
                'Branch belongs to a different project root.'
            )
            return

    shutil.rmtree(
        bdir
    )

    result['status'] = 'APPLIED'
    result['message'] = (
        "Branch '%s' deleted"
        % name
    )


def execute(ctx, parsed_op, result):
    args = ((parsed_op.get('directives') or {}).get('ARGS') or parsed_op.get('target') or '').strip()
    parts = args.split(None, 1)
    sub = parts[0]
    name = parts[1].strip() if len(parts) > 1 else ''

    if sub == 'create':
        _create(ctx, result, name, parsed_op.get('body') or '')
    elif sub == 'restore':
        _restore(ctx, result, name)
    elif sub == 'list':
        _list(ctx, result)
    elif sub == 'delete':
        _delete(ctx, result, name)
    else:
        result['status'] = 'FAILED_PARSE'
        result['message'] = 'Unknown BRANCH subcommand: ' + sub
