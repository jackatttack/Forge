# -*- coding: utf-8 -*-
"""
Portable Forge launcher for Pythonista.

Forge itself is installed in site-packages.

This file is the Pythonista host wrapper:
clipboard input -> Forge -> canonical clipboard packet.

Live console presentation is supplied by the packaged Pythonista adapter
forge.adapters.pythonista.console_ui.
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


def _clipboard_safe_text(text):
    """
    Return text Pythonista's clipboard bridge can safely accept.

    Pythonista rejects strings containing literal NUL characters. Preserve the
    information visibly instead of allowing one bad run artifact to crash the
    launcher after Forge has already completed the run.
    """
    return str(
        text
        or ''
    ).replace(
        '\x00',
        r'\x00',
    )


def set_result_text(text):
    clipboard.set(
        _clipboard_safe_text(
            text
        )
    )


def progress_renderer():
    """
    Forge's console renderer, wrapped so the Forge Landing docks when the run
    starts and fills in live. If the landing cannot load, the renderer keeps
    its classic live console redraw instead.
    """
    try:
        from forge.adapters.pythonista.console_ui import ForgeConsoleUI
    except Exception:
        return None
    try:
        from forge.adapters.pythonista.landing.hook import make_listener
        return make_listener(ForgeConsoleUI(live=False))
    except Exception:
        return ForgeConsoleUI()


def show_landing(run, progress):
    """
    Dock the Forge Landing over the console after the run.

    Presentation only: if it cannot load or dock, the console keeps the
    text summary Forge already printed.
    """
    try:
        from forge.adapters.pythonista.landing.hook import show_after_run
        show_after_run(run, progress)
    except Exception:
        pass


def editor_tab_sync():
    """
    Keep open Pythonista editor tabs in step with files Forge writes.

    Registers forge.adapters.pythonista.editor_tabs with core's host hooks.
    Never required for Forge correctness: if it cannot load, Forge writes
    files exactly as before.
    """
    try:
        from forge.adapters.pythonista.editor_tabs import register_with_forge
        register_with_forge()
    except Exception:
        pass



def main():
    bundle = get_bundle_text()

    if not bundle.strip():
        print(
            'Forge: clipboard contains no bundle text.'
        )
        return

    editor_tab_sync()
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
        show_landing(
            run,
            progress,
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