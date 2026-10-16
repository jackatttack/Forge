# -*- coding: utf-8 -*-
"""
Portable Forge bootstrap for Juno.

Installs or updates Forge from the current GitHub main branch. Like the
other bootstraps it contains no installation logic of its own:

    download install.py
    ->
    run install.py --github jackatttack/Forge --ref main
                   --juno-documents <Documents> --force

The repository-root install.py remains the authoritative installer. This
file only finds Juno's Documents folder, which a notebook may sit below.
"""

from __future__ import print_function

import os
import runpy
import sys
import tempfile
import urllib.request


REPOSITORY = 'jackatttack/Forge'
REF = 'main'


def documents_folder():
    """Juno's Documents folder, from wherever this notebook is running."""
    start = os.path.abspath(os.getcwd())
    if start.startswith('/.nofollow/'):
        start = start[len('/.nofollow'):]

    folder = start
    while os.path.basename(folder) != 'Documents':
        parent = os.path.dirname(folder)
        if parent == folder:
            return start
        folder = parent
    return folder


def main():
    installer_url = (
        'https://raw.githubusercontent.com/'
        + REPOSITORY
        + '/'
        + REF
        + '/install.py'
    )

    documents = documents_folder()

    print('Portable Forge — Juno GitHub bootstrap')
    print('======================================')
    print('repository:', REPOSITORY)
    print('ref:', REF)
    print('Documents:', documents)
    print('')
    print('Downloading installer from GitHub...')

    with urllib.request.urlopen(installer_url) as response:
        source = response.read()

    descriptor, installer_path = tempfile.mkstemp(
        prefix='portable_forge_juno_',
        suffix='.py',
    )
    os.close(descriptor)

    with open(installer_path, 'wb') as handle:
        handle.write(source)

    old_argv = list(sys.argv)
    install_code = 0

    try:
        sys.argv = [
            installer_path,
            '--github',
            REPOSITORY,
            '--ref',
            REF,
            '--juno-documents',
            documents,
            '--force',
        ]

        try:
            runpy.run_path(installer_path, run_name='__main__')
        except SystemExit as exc:
            install_code = exc.code if exc.code is not None else 0

    finally:
        sys.argv = old_argv
        try:
            os.remove(installer_path)
        except OSError:
            pass

    if install_code not in (0, None):
        raise RuntimeError(
            'Portable Forge installer failed with code %r.' % install_code
        )

    print('')
    print('Juno GitHub bootstrap complete.')
    print('Restart the Juno kernel if Forge was imported earlier.')
    print('Then put a Forge bundle on the clipboard and run:')
    print('  forge_entry.py')


if __name__ == '__main__':
    main()