# -*- coding: utf-8 -*-
"""
Which app is running Forge: pythonista, pythonide or unknown.

Identity only, read from sys.executable; no paths and no configuration.
Used to print App: in the packet and to check an optional ENV: header
(see forge/core/preparse.py). PythonIDE's PYTHONIDE environment variable
is not used: it is set when Forge runs bundles but not when scripts run
by hand, so it cannot be relied on.
"""

import sys

KNOWN_APPS = ('pythonista', 'pythonide', 'juno')


def detect_app():
    """Return 'pythonista', 'pythonide' or 'unknown'."""
    executable = str(sys.executable or '')
    if 'Python IDE' in executable:
        return 'pythonide'
    if 'Pythonista' in executable:
        return 'pythonista'
    return 'unknown'