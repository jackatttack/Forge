# -*- coding: utf-8 -*-
# portable-forge-pythonide-launcher-v1
"""
Portable Forge clipboard bridge for PythonIDE.

Workflow:
1. Copy a Forge bundle.
2. Run forge-entry.py from the PythonIDE workspace.
3. Forge executes against the current working directory.
4. The canonical return packet is copied back to the clipboard.

When Rich is available, forge_live_ui.py provides the live dashboard.
"""

import os
import traceback

import clipboard
import forge


MODE = "dev"
STORE_RUN = True

PROJECT_ROOT = os.getcwd()
FORGE_HOME = os.path.join(
    PROJECT_ROOT,
    ".forge",
)


class PlainProgress:
    """Small fallback when the Rich PythonIDE dashboard is unavailable."""

    def __call__(self, event):
        name = str(
            event.get("event")
            or ""
        )

        if name == "parse_started":
            print("Parsing Forge bundle...")
            return

        if name == "parse_finished":
            if event.get("success"):
                print(
                    "Parsed: {} operation(s)".format(
                        event.get("op_count") or 0
                    )
                )
            else:
                print(
                    "Parse failed: {} error(s)".format(
                        event.get("error_count") or 0
                    )
                )
            return

        if name == "operation_started":
            print(
                "-> {}/{} {} {}".format(
                    event.get("index"),
                    event.get("total"),
                    event.get("op"),
                    event.get("target") or "",
                ).rstrip()
            )
            return

        if name == "operation_finished":
            print(
                "<- {}/{} {} [{}]".format(
                    event.get("index"),
                    event.get("total"),
                    event.get("op"),
                    event.get("status"),
                )
            )
            return

        if name == "run_finished":
            print(
                "Forge complete: {}".format(
                    event.get("status")
                )
            )

    def abort(self):
        print("Forge bridge failed.")

    def print_clipboard_status(self, ok):
        if ok:
            print(
                "Forge return packet copied to clipboard. "
                "Paste it back into ChatGPT."
            )
        else:
            print(
                "Forge ran, but PythonIDE could not update "
                "the clipboard."
            )


def make_progress():
    try:
        from forge_live_ui import ForgeLiveUI

        return ForgeLiveUI()

    except Exception:
        return PlainProgress()


def main():
    print("=== FORGE CLIPBOARD BRIDGE ===")
    print("Project root:", PROJECT_ROOT)
    print("Forge home:  ", FORGE_HOME)
    print()

    try:
        bundle = clipboard.get()

    except Exception:
        message = (
            "=== FORGE BRIDGE ERROR ===\n\n"
            "Could not read the clipboard.\n\n"
            + traceback.format_exc()
        )
        print(message)
        return

    if not bundle or not bundle.strip():
        message = (
            "=== FORGE BRIDGE ERROR ===\n\n"
            "Clipboard is empty.\n"
            "Copy a Forge bundle first, then run this script again."
        )

        try:
            clipboard.set(
                message
            )
        except Exception:
            pass

        print(
            message
        )
        return

    print(
        "Clipboard input: {} characters".format(
            len(bundle)
        )
    )
    print("Running Forge...")
    print()

    try:
        os.makedirs(
            FORGE_HOME,
            exist_ok=True,
        )

    except Exception:
        packet = (
            "=== FORGE BRIDGE ERROR ===\n\n"
            "Could not create Forge home:\n"
            "{}\n\n".format(FORGE_HOME)
            + traceback.format_exc()
        )

        try:
            clipboard.set(
                packet
            )
        except Exception:
            pass

        print(
            packet
        )
        return

    progress = make_progress()

    try:
        run = forge.run_text(
            bundle,
            project_root=PROJECT_ROOT,
            forge_home=FORGE_HOME,
            mode=MODE,
            store=STORE_RUN,
            on_event=progress,
        )

        packet = forge.render_standard(
            run
        )

    except Exception:
        if hasattr(
            progress,
            "abort",
        ):
            try:
                progress.abort()
            except Exception:
                pass

        packet = (
            "=== FORGE BRIDGE ERROR ===\n\n"
            + traceback.format_exc()
        )

    try:
        clipboard.set(
            packet
        )
        clipboard_ok = True

    except Exception:
        clipboard_ok = False

    if hasattr(
        progress,
        "print_clipboard_status",
    ):
        progress.print_clipboard_status(
            clipboard_ok
        )

    elif clipboard_ok:
        print(
            "Forge return packet copied to clipboard."
        )

    else:
        print(
            packet
        )
        print(
            "PythonIDE could not update the clipboard."
        )


if __name__ == "__main__":
    main()