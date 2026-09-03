# -*- coding: utf-8 -*-
"""
Portable Forge bootstrap for Pythonista.

The bootstrap installs the current Portable Forge main branch.

It resolves main to one immutable commit before downloading anything, then
uses that same commit for both install.py and the package archive. This keeps
a bootstrap install snapshot-consistent even if main advances mid-install.
"""

import json
import os
import runpy
import sys
import tempfile
import urllib.parse
import urllib.request


REPOSITORY = 'jackatttack/Forge'
REF = 'main'
USER_AGENT = 'portable-forge-pythonista-bootstrap'


def _valid_commit_sha(value):
    value = str(
        value
        or ''
    ).strip()

    return (
        len(value) == 40
        and all(
            char in '0123456789abcdefABCDEF'
            for char in value
        )
    )


def resolve_ref(repository, ref):
    repository = str(
        repository
        or ''
    ).strip().strip('/')

    ref = str(
        ref
        or ''
    ).strip()

    if repository.count('/') != 1:
        raise RuntimeError(
            'Bootstrap repository must use OWNER/REPOSITORY.'
        )

    if not ref:
        raise RuntimeError(
            'Bootstrap ref cannot be empty.'
        )

    url = (
        'https://api.github.com/repos/'
        + repository
        + '/commits/'
        + urllib.parse.quote(
            ref,
            safe='',
        )
    )

    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': USER_AGENT,
        },
    )

    with urllib.request.urlopen(
        request
    ) as response:
        payload = json.loads(
            response.read().decode('utf-8')
        )

    commit = str(
        payload.get('sha')
        or ''
    ).strip()

    if not _valid_commit_sha(
        commit
    ):
        raise RuntimeError(
            'GitHub did not return a valid commit SHA for %s@%s.'
            % (
                repository,
                ref,
            )
        )

    return commit


def main():
    resolved_commit = resolve_ref(
        REPOSITORY,
        REF,
    )

    installer_url = (
        'https://raw.githubusercontent.com/'
        + REPOSITORY
        + '/'
        + resolved_commit
        + '/install.py'
    )

    print(
        'Portable Forge bootstrap source:'
    )
    print(
        'Repository:',
        REPOSITORY,
    )
    print(
        'Requested ref:',
        REF,
    )
    print(
        'Resolved commit:',
        resolved_commit,
    )
    print('')
    print(
        'Downloading Portable Forge installer...'
    )

    with urllib.request.urlopen(
        installer_url
    ) as response:
        source = response.read()

    descriptor, installer_path = tempfile.mkstemp(
        prefix='portable_forge_install_',
        suffix='.py',
    )

    os.close(
        descriptor
    )

    with open(
        installer_path,
        'wb',
    ) as handle:
        handle.write(
            source
        )

    old_argv = list(
        sys.argv
    )

    install_code = 0

    try:
        sys.argv = [
            installer_path,
            '--github',
            REPOSITORY,
            '--ref',
            resolved_commit,
            '--requested-ref',
            REF,
            '--force',
        ]

        try:
            runpy.run_path(
                installer_path,
                run_name='__main__',
            )

        except SystemExit as exc:
            install_code = (
                exc.code
                if exc.code is not None
                else 0
            )

    finally:
        sys.argv = old_argv

        try:
            os.remove(
                installer_path
            )
        except OSError:
            pass

    if install_code not in (
        0,
        None,
    ):
        raise RuntimeError(
            'Portable Forge installer failed with code %r.'
            % install_code
        )

    print('')
    print(
        'Portable Forge bootstrap complete.'
    )


if __name__ == '__main__':
    main()
