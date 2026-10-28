# -*- coding: utf-8 -*-
"""
Keep Pythonista's open editor tabs in step with files Forge writes.

Pythonista holds an open tab's text in memory. When Forge rewrote a file
on disk, a background tab kept the old text, and running that tab could
put the old version back (2026-10-28). The Pythonista launcher registers
this module's hooks with forge.core.host_hooks:

- before a write: refuse if a loaded tab's text differs from the disk
  (unsaved edits or a stale copy), so nothing is silently lost;
- after a write: put the new disk text into every loaded tab for that
  file, replacing only the span that changed, so the cursor and scroll
  stay put where they can.

Tabs whose view never loaded are skipped: they read the disk when shown.
Text view positions count UTF-16 units, so most emoji count as two.

This reaches Pythonista's private editor objects, the same route
editor.replace_text takes for the active tab. If an update changes them,
no tabs are found and Forge writes exactly as it did before.
"""

import os

from forge.core.host_hooks import HostRefusal, register


def utf16_length(text):
    return len(text.encode('utf-16-le')) // 2


def without_final_newline(text):
    """The editor may hold one more trailing newline than the disk."""
    return text[:-1] if text.endswith('\n') else text


def changed_span(old, new):
    """
    Return (start, old_end, new_end): old[start:old_end] becomes
    new[start:new_end], the smallest middle part that differs.
    """
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    common_end = 0
    while (
        common_end < limit - start
        and old[len(old) - 1 - common_end] == new[len(new) - 1 - common_end]
    ):
        common_end += 1
    return start, len(old) - common_end, len(new) - common_end


class PythonistaTab(object):
    """One loaded editor tab, reached through its text view on the main thread."""

    def __init__(self, path, controller):
        self.path = path
        self._controller = controller

    def text(self):
        from objc_util import on_main_thread

        @on_main_thread
        def read():
            return str(self._controller.editorView().textView().text())
        return read()

    def replace(self, start, end, new_text):
        """Replace UTF-16 positions start..end of the buffer with new_text."""
        from objc_util import NSRange, ObjCClass, on_main_thread

        @on_main_thread
        def apply():
            text_view = self._controller.editorView().textView()
            span = ObjCClass('OMTextRange').rangeWithNSRange_(
                NSRange(start, end - start)
            )
            text_view.replaceRange_withText_(span, new_text)
        apply()


def pythonista_tabs():
    """Every loaded text tab; [] outside Pythonista."""
    try:
        from objc_util import ObjCClass, on_main_thread
    except ImportError:
        return []

    @on_main_thread
    def collect():
        application = ObjCClass('UIApplication').sharedApplication()
        root = application.keyWindow().rootViewController()
        editor_class = ObjCClass('PA2UniversalTextEditorViewController')
        tabs = []
        for controller in root.detailViewController().tabViewControllers():
            if controller.isKindOfClass_(editor_class) and controller.isViewLoaded():
                path = os.path.realpath(str(controller.filePath()))
                tabs.append(PythonistaTab(path, controller))
        return tabs
    return collect()


# Where tabs come from. Tests replace this with a function returning fakes.
tab_source = pythonista_tabs


def tabs_for(path):
    """Loaded tabs showing path; [] if the editor cannot be reached."""
    target = os.path.realpath(path)
    try:
        return [tab for tab in tab_source() if tab.path == target]
    except Exception:
        return []


def read_disk(path):
    """The file's UTF-8 text, or None if it is missing or not text."""
    try:
        with open(path, 'rb') as handle:
            return handle.read().decode('utf-8')
    except (OSError, UnicodeDecodeError):
        return None


def before_write(path):
    """Refuse the write if an open tab's text differs from the disk."""
    disk = read_disk(path)
    if disk is None:
        return  # a new file, or not text: no tab edits worth protecting
    for tab in tabs_for(path):
        try:
            buffer = tab.text()
        except Exception:
            continue
        if without_final_newline(buffer) != without_final_newline(disk):
            raise HostRefusal(
                '%s is open in a Pythonista editor tab whose text differs '
                'from the file on disk (unsaved edits or a stale copy). '
                'Close or reload that tab, then rerun.' % os.path.basename(path)
            )


def after_write(path):
    """Put the file's new text into every loaded tab that shows it."""
    tabs = tabs_for(path)
    if not tabs:
        return
    new_text = read_disk(path)
    if new_text is None:
        return
    for tab in tabs:
        old_text = tab.text()
        if old_text == new_text:
            continue
        start, old_end, new_end = changed_span(old_text, new_text)
        tab.replace(
            utf16_length(old_text[:start]),
            utf16_length(old_text[:old_end]),
            new_text[start:new_end],
        )


def register_with_forge():
    """Called by the Pythonista launcher at startup."""
    register(before_write=before_write, after_write=after_write)
