# -*- coding: utf-8 -*-
"""
Portable Forge bootstrap for Pythonista.

The stable bootstrap is pinned to the Portable Forge v0.1.1 release.

The bootstrap has one job:

    download install.py
    ->
    run install.py

The installer itself detects Pythonista, chooses site-packages-3, installs the
runtime, creates the root forge_entry.py launcher, and opens a newly created
launcher on first installation.
"""

import os
import runpy
import sys
import tempfile
import urllib.request


REPOSITORY = 'jackatttack/Forge'
REF = 'v0.1.1'


def main():
    installer_url = (
        'https://raw.githubusercontent.com/'
        + REPOSITORY
        + '/'
        + REF
        + '/install.py'
    )

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
            REF,
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