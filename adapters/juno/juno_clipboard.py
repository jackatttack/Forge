# -*- coding: utf-8 -*-
# portable-forge-juno-clipboard-v1
"""
Clipboard for Juno, which has no clipboard module.

Talks to iOS UIPasteboard through the Objective-C runtime with ctypes only.
Same get()/set() shape as Pythonista's clipboard, so the Forge entry script
reads the same in every app. Proven on device 2026-10-16.
"""

import ctypes

# The Objective-C runtime is already loaded in the app; no library path needed.
_objc = ctypes.CDLL(None)
_objc.objc_getClass.restype = ctypes.c_void_p
_objc.objc_getClass.argtypes = [ctypes.c_char_p]
_objc.sel_registerName.restype = ctypes.c_void_p
_objc.sel_registerName.argtypes = [ctypes.c_char_p]
_MSG_SEND = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value


def _send(receiver, selector, restype, argtypes=(), *args):
    """Call one Objective-C method.

    objc_msgSend is cast to an exact function type per call: on arm64 it
    must not be called as a variadic function.
    """
    function = ctypes.CFUNCTYPE(
        restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes
    )(_MSG_SEND)
    return function(receiver, _objc.sel_registerName(selector), *args)


def _pasteboard():
    return _send(_objc.objc_getClass(b"UIPasteboard"), b"generalPasteboard",
                 ctypes.c_void_p)


def get():
    """Return the clipboard's text, or '' when it holds none."""
    ns_string = _send(_pasteboard(), b"string", ctypes.c_void_p)
    if not ns_string:
        return ""
    return _send(ns_string, b"UTF8String", ctypes.c_char_p).decode("utf-8")


def set(text):
    """Put text on the clipboard."""
    ns_string = _send(_objc.objc_getClass(b"NSString"),
                      b"stringWithUTF8String:", ctypes.c_void_p,
                      (ctypes.c_char_p,), str(text).encode("utf-8"))
    _send(_pasteboard(), b"setString:", None, (ctypes.c_void_p,), ns_string)