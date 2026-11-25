"""Run Forge: run the bundle on the clipboard, the way the wrench menu does.

Role: run · Part of: anvil/run_forge · Entry

The Run page's Run Forge button. It opens Pythonista's own URL for the
launcher (forge_entry.py in Documents), so the run starts as a fresh script
like any other run, and Anvil fills in with it as usual. Nothing runs inside
the tap: a tap that ran Forge itself would hold the main thread that
Anvil's live run view needs.
"""
import webbrowser
from urllib.parse import quote


# --- Settings ---------------------------------------------------------------

LAUNCHER = 'forge_entry.py'             # the Forge launcher, relative to Documents
EMPTY_NOTE = 'Clipboard is empty: copy a bundle first'


def launcher_url(launcher=LAUNCHER):
    """Pythonista's URL that runs launcher."""
    return 'pythonista3://%s?action=run' % quote(launcher)


def run_clipboard_bundle(say=print):
    """Start a Forge run of the clipboard. Returns False, and says why, when
    the clipboard holds no text. If the clipboard cannot be read here, the
    launcher is started anyway and makes the same check itself."""
    try:
        from forge.adapters.pythonista import pasteboard
        text = pasteboard.get_text() or ''
    except Exception:
        text = None
    if text is not None and not text.strip():
        say(EMPTY_NOTE)
        return False
    webbrowser.open(launcher_url())
    return True