# -*- coding: utf-8 -*-
"""
Minimal Portable Forge launcher for Pythonista.

Forge itself is installed in site-packages.

This file is only the Pythonista host wrapper.
Change PROJECT_ROOT or replace the clipboard functions however you like.
"""

import os

import clipboard
import forge


PORTABLE_FORGE_PYTHONISTA_LAUNCHER = 'portable-forge-pythonista-launcher-v1'


PROJECT_ROOT = os.path.abspath(
    os.path.expanduser(
        '~/Documents'
    )
)


def get_bundle_text():
    return str(
        clipboard.get()
        or ''
    )


def set_result_text(text):
    clipboard.set(
        text
    )

    print(
        text,
        end='',
    )


def main():
    bundle = get_bundle_text()

    if not bundle.strip():
        print(
            'Forge: clipboard contains no bundle text.'
        )
        return

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    result = forge.render_standard(
        run
    )

    set_result_text(
        result
    )


if __name__ == '__main__':
    main()