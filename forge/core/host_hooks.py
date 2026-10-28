# -*- coding: utf-8 -*-
"""
Host hooks: let a host adapter react to files Forge writes, without core
knowing which host it runs on.

Core calls before_write(path) just before it replaces a file and
after_write(path) just after. Nothing is registered by default, so on a
host without an adapter both are no-ops and writes behave as they always
did. The Pythonista launcher registers forge.adapters.pythonista.editor_tabs,
which keeps open editor tabs in step with the disk.

A before hook may raise HostRefusal to stop a write; the file is then left
untouched. Any other hook error is swallowed: a broken hook must never
block a write, and after a write the disk change has already happened.
"""

import os


class HostRefusal(OSError):
    """A host refused a write, e.g. the file differs in an open editor tab."""


_before_write = []
_after_write = []


def register(before_write=None, after_write=None):
    """Add hooks. Registering the same function twice has no extra effect."""
    if before_write is not None and before_write not in _before_write:
        _before_write.append(before_write)
    if after_write is not None and after_write not in _after_write:
        _after_write.append(after_write)


def clear():
    """Remove every hook. For tests, and for hosts that unload an adapter."""
    del _before_write[:]
    del _after_write[:]


def before_write(path):
    """Run before hooks. Only HostRefusal escapes."""
    path = os.path.abspath(path)
    for hook in list(_before_write):
        try:
            hook(path)
        except HostRefusal:
            raise
        except Exception:
            pass


def after_write(path):
    """Run after hooks. Nothing escapes: the write has already happened."""
    path = os.path.abspath(path)
    for hook in list(_after_write):
        try:
            hook(path)
        except Exception:
            pass
