# -*- coding: utf-8 -*-
"""
Read and write the iOS clipboard without freezing Pythonista.

Pythonista's clipboard module, called from a script thread, waits for the
main thread while it still holds Python's lock. If the main thread needs
Python at that moment (a docked view's update(), such as the Forge Landing
ticking 30 times a second, or any objc_util callback), neither thread can
go on and Pythonista freezes with no error.

Found 2026-11-06 with labs/landing_stress/console_clear_lab.py: the module
route froze within about 500 packet-sized writes as soon as anything ran
Python on the main thread, while UIPasteboard through objc_util ran 2000
writes clean under a 30 Hz ticker. objc_util calls go through ctypes, which
releases Python's lock while the call waits.

Falls back to the clipboard module only where objc_util is missing.
"""


def _pasteboard():
    """UIPasteboard's general pasteboard. Tests replace this."""
    from objc_util import ObjCClass
    return ObjCClass('UIPasteboard').generalPasteboard()


def get_text():
    """The clipboard's text, or '' when it holds none. Never raises."""
    try:
        value = _pasteboard().string()
        return '' if value is None else str(value)
    except Exception:
        pass
    try:
        import clipboard
        return str(clipboard.get() or '')
    except Exception:
        return ''


def set_text(text):
    """Put text on the clipboard."""
    text = '' if text is None else str(text)
    try:
        _pasteboard().setString_(text)
        return
    except Exception:
        pass
    import clipboard
    clipboard.set(text)