# -*- coding: utf-8 -*-
"""
Portable Forge launcher for Pythonista.

Forge itself is installed in site-packages.

This file is the Pythonista host wrapper:
clipboard input -> Forge -> canonical clipboard packet.

Live console presentation is supplied by the separate Pythonista adapter
forge_console_ui.py.
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


def progress_renderer():
    try:
        from forge_console_ui import ForgeConsoleUI
        return ForgeConsoleUI()
    except Exception:
        return None


def attach_local_extensions():
    """
    Attach optional host-local Forge extensions.

    Portable Forge does not depend on forge_local. A Pythonista workspace may
    provide ~/Documents/forge_local/loader.py to extend the normal custom-op
    discovery path without modifying the installed runtime.
    """
    local_root = os.path.join(
        PROJECT_ROOT,
        'forge_local',
    )

    if not os.path.isdir(
        local_root
    ):
        return []

    try:
        from forge_local.loader import attach_local_ops
    except Exception:
        return []

    return attach_local_ops(
        PROJECT_ROOT
    )


def main():
    bundle = get_bundle_text()

    if not bundle.strip():
        print(
            'Forge: clipboard contains no bundle text.'
        )
        return

    attach_local_extensions()

    progress = progress_renderer()

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
        on_event=progress,
    )

    result = forge.render_standard(
        run
    )

    set_result_text(
        result
    )

    if (
        progress is not None
        and hasattr(
            progress,
            'print_clipboard_status',
        )
    ):
        progress.print_clipboard_status(
            True
        )
    else:
        # Presentation must never be required for Forge correctness.
        # If the richer Pythonista adapter is unavailable, retain the old
        # behaviour and show the canonical packet directly.
        print(
            result,
            end='',
        )


if __name__ == '__main__':
    main()