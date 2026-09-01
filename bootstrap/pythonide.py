# -*- coding: utf-8 -*-
"""
Portable Forge bootstrap for PythonIDE.

This development bootstrap installs directly from the current GitHub main
branch rather than PyPI.

It deliberately contains no installation logic of its own:

    download install.py
    ->
    run install.py --github jackatttack/Forge --ref main

The repository-root install.py remains the authoritative installer.
"""

from __future__ import print_function

import os
import runpy
import sys
import tempfile
import urllib.request


REPOSITORY = 'jackatttack/Forge'
REF = 'main'


def main():
    installer_url = (
        'https://raw.githubusercontent.com/'
        + REPOSITORY
        + '/'
        + REF
        + '/install.py'
    )

    print('Portable Forge — PythonIDE GitHub bootstrap')
    print('===========================================')
    workspace = os.path.abspath(
        os.getcwd()
    )

    print('repository:', REPOSITORY)
    print('ref:', REF)
    print('workspace:', workspace)
    print('')
    print('Downloading installer from GitHub...')

    with urllib.request.urlopen(
        installer_url
    ) as response:
        source = response.read()

    descriptor, installer_path = tempfile.mkstemp(
        prefix='portable_forge_pythonide_',
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
            '--pythonide-workspace',
            workspace,
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
    print('PythonIDE GitHub bootstrap complete.')
    print('')
    print('Installed runtime and PythonIDE adapter into:')
    print(' ', workspace)
    print('')
    print('Restart the Python interpreter if Forge was imported earlier.')
    print('Then put a Forge bundle on the clipboard and run:')
    print('  forge-entry.py')


if __name__ == '__main__':
    main()