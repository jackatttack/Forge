# -*- coding: utf-8 -*-
# portable-forge-juno-launcher-v1
"""
Portable Forge clipboard bridge for Juno.

1. Copy a Forge bundle.
2. Run forge_entry.py from Juno's Documents folder (a Shortcut can do it).
3. Forge runs against Documents; its state lives in Documents/.forge.
4. The packet is copied back to the clipboard.

Juno has no clipboard module, so juno_clipboard.py, installed next to this
file, reaches iOS UIPasteboard through ctypes.
"""

import os
import sys
import traceback

MODE = "dev"
STORE_RUN = True


def documents_folder():
    """Return Juno's Documents folder, however this script was started.

    A Shortcut run reports paths with an iOS '/.nofollow' prefix and may
    start in another folder; a notebook run has no __file__. Falls back to
    the starting folder when no Documents folder is above it.
    """
    try:
        start = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        start = os.getcwd()
    if start.startswith("/.nofollow/"):
        start = start[len("/.nofollow"):]

    folder = start
    while os.path.basename(folder) != "Documents":
        parent = os.path.dirname(folder)
        if parent == folder:
            return start
        folder = parent
    return folder


PROJECT_ROOT = documents_folder()
FORGE_HOME = os.path.join(PROJECT_ROOT, ".forge")

# The installer puts Forge in Documents/site-packages and juno_clipboard.py
# in Documents; make both importable whatever Juno's sys.path holds.
for _path in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "site-packages")):
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

import juno_clipboard as clipboard  # noqa: E402
import forge  # noqa: E402


def set_clipboard(text):
    try:
        clipboard.set(text)
        return True
    except Exception:
        return False


def main():
    print("=== FORGE CLIPBOARD BRIDGE (Juno) ===")
    print("Project root:", PROJECT_ROOT)

    try:
        bundle = clipboard.get()
    except Exception:
        print("Could not read the clipboard.\n" + traceback.format_exc())
        return

    if not bundle.strip():
        message = ("=== FORGE BRIDGE ERROR ===\n\nClipboard is empty.\n"
                   "Copy a Forge bundle first, then run this again.")
        set_clipboard(message)
        print(message)
        return

    try:
        # ops/ exists so FORGE config does not warn about a missing ops root.
        os.makedirs(os.path.join(FORGE_HOME, "ops"), exist_ok=True)
        run = forge.run_text(
            bundle,
            project_root=PROJECT_ROOT,
            forge_home=FORGE_HOME,
            mode=MODE,
            store=STORE_RUN,
        )
        packet = forge.render_standard(run)
    except Exception:
        packet = "=== FORGE BRIDGE ERROR ===\n\n" + traceback.format_exc()

    if set_clipboard(packet):
        print("Forge return packet copied to clipboard.")
    else:
        print(packet)
        print("Juno could not update the clipboard.")


if __name__ == "__main__":
    main()