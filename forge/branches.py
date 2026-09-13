# -*- coding: utf-8 -*-
"""
Standalone viewer for stored Forge branch checkpoints.

Branch checkpoints live under the Forge home, which on iOS is a hidden
directory outside anything Pythonista's file browser or the Files app can
reach. Each branch already contains a self-contained restore_branch.py,
but finding one means having kept the path from an old run packet.

This module lists every branch it can find and points at its restore
script, so recovery does not depend on remembering a path.

It deliberately imports no part of Forge. If Forge is broken, this must
still run. Usage:

    python3 -m forge.branches

Inside Pythonista the printed restore scripts become tappable links.
Elsewhere the ready-to-run command is printed instead.
"""

import json
import os
import sys

try:
    import console
except Exception:
    console = None


BRANCHES_SUBPATH = os.path.join('artifacts', 'branches')

# Recovery usually wants the newest checkpoints, and a phone console
# scrolls badly. "all" overrides this.
DEFAULT_SHOWN = 10


def candidate_forge_homes():
    """
    Return plausible Forge home locations, most likely first.

    Discovery is explicit rather than clever: this reports where it looked
    so a failed search is diagnosable instead of mysterious.
    """
    here = os.path.dirname(os.path.abspath(__file__))

    candidates = []

    # Installed under <host>/site-packages-N/forge/, with .forge a sibling
    # of the Documents directory that contains site-packages.
    package_parent = os.path.dirname(here)
    documents = os.path.dirname(package_parent)
    host = os.path.dirname(documents)

    candidates.append(os.path.join(host, '.forge'))
    candidates.append(os.path.join(documents, '.forge'))
    candidates.append(os.path.join(os.getcwd(), '.forge'))
    candidates.append(os.path.join(os.path.expanduser('~'), '.forge'))

    seen = set()
    unique = []
    for path in candidates:
        resolved = os.path.abspath(path)
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def find_branch_locations(explicit=None):
    """
    Return (locations, searched) where locations is every branches
    directory found.

    This deliberately does not stop at the first hit. More than one Forge
    home can exist on a machine — a current one and a stale one from an
    older layout — and silently picking one would let a recovery session
    conclude a checkpoint was lost when it is simply somewhere else.
    """
    if explicit:
        home = os.path.abspath(explicit)
        root = os.path.join(home, BRANCHES_SUBPATH)
        found = [root] if os.path.isdir(root) else []
        return found, [home]

    searched = []
    found = []

    for home in candidate_forge_homes():
        searched.append(home)
        root = os.path.join(home, BRANCHES_SUBPATH)
        if os.path.isdir(root) and root not in found:
            found.append(root)

    return found, searched


def read_branch(directory):
    """Return one branch summary dict, tolerating a damaged manifest."""
    name = os.path.basename(directory)
    manifest_path = os.path.join(directory, 'manifest.json')
    restore_path = os.path.join(directory, 'restore_branch.py')

    summary = {
        'name': name,
        'directory': directory,
        'restore_script': restore_path if os.path.isfile(restore_path) else '',
        'created': '',
        'project_root': '',
        'file_count': 0,
        'problem': '',
    }

    if not os.path.isfile(manifest_path):
        summary['problem'] = 'no manifest.json'
        return summary

    try:
        with open(manifest_path, 'r', encoding='utf-8') as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        summary['problem'] = 'unreadable manifest: %s' % (error,)
        return summary

    summary['created'] = str(manifest.get('created') or '')
    summary['project_root'] = str(
        manifest.get('project_root') or manifest.get('root') or ''
    )
    summary['file_count'] = len(manifest.get('files') or [])
    return summary


def collect_branches(branches_root):
    """Return every branch summary, newest first where dates allow."""
    entries = []
    for name in sorted(os.listdir(branches_root)):
        directory = os.path.join(branches_root, name)
        if os.path.isdir(directory):
            entries.append(read_branch(directory))

    entries.sort(key=lambda item: item['created'], reverse=True)
    return entries


def link(path):
    """Return a tappable Pythonista link, or the plain path elsewhere."""
    if console is None or not path:
        return path
    return 'pythonista3://' + path.lstrip('/')


def report(branches, branches_root, limit=None):
    """
    Print the branch list and how to restore one.

    A long list is worse than a short one during recovery: the newest
    checkpoints are almost always the relevant ones, and a phone console
    scrolls badly. The rest stay one argument away.
    """
    shown = branches if limit is None else branches[:limit]

    print('Forge branches')
    print('location: %s' % branches_root)
    print('count: %d' % len(branches))

    if len(shown) < len(branches):
        print('showing: %d most recent (pass "all" to see every branch)'
              % len(shown))

    print('')

    for entry in shown:
        print(entry['name'])

        if entry['problem']:
            print('  PROBLEM: %s' % entry['problem'])

        if entry['created']:
            print('  created: %s' % entry['created'])

        print('  files:   %d' % entry['file_count'])

        if entry['project_root']:
            print('  restores into: %s' % entry['project_root'])

        if entry['restore_script']:
            print('  restore: %s' % link(entry['restore_script']))
        else:
            print('  restore: MISSING restore_branch.py')

        print('')

    if console is not None:
        print('Tap a restore path to open it in Pythonista, then run it.')
    else:
        print('To restore, run:  python3 <restore path>')

    print('A restore overwrites captured files in the project root shown.')


def main(argv=None):
    """
    List stored branches.

    Arguments, in any order:
        all              show every branch instead of the recent ones
        <path>           an explicit Forge home to inspect
    """
    argv = list(argv if argv is not None else sys.argv[1:])

    show_all = any(item.strip().lower() == 'all' for item in argv)
    paths = [item for item in argv if item.strip().lower() != 'all']
    explicit = paths[0] if paths else None
    limit = None if show_all else DEFAULT_SHOWN

    locations, searched = find_branch_locations(explicit)

    if not locations:
        print('No Forge branches directory found.')
        print('Looked in:')
        for path in searched:
            print('  %s' % path)
        print('')
        print('Pass a Forge home explicitly:')
        print('  python3 -m forge.branches /path/to/.forge')
        return 1

    if len(locations) > 1:
        print('NOTE: %d Forge branch stores found.' % len(locations))
        print('One may be stale. Every store is listed below.')
        print('')

    total = 0

    for branches_root in locations:
        branches = collect_branches(branches_root)
        total += len(branches)

        if not branches:
            print('Forge branches')
            print('location: %s' % branches_root)
            print('count: 0')
            print('')
            continue

        report(branches, branches_root, limit=limit)
        print('')

    if not total:
        print('No branches stored in any location found.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())