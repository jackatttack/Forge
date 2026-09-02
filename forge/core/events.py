# -*- coding: utf-8 -*-
"""
Lightweight execution events for Portable Forge.

Forge Core emits structured facts. Hosts decide how, or whether, to present
them.

The event callback is deliberately optional and isolated from execution:
a broken progress renderer must never be able to break a Forge run.
"""


def emit_event(on_event, event, **fields):
    """
    Send one structured event to ``on_event``.

    ``on_event`` should be a callable accepting one dictionary. Event payloads
    are intentionally small and presentation-neutral so hosts can render them
    as plain text, Rich terminal output, UIKit/AppUI views, logs, or nothing.

    Callback exceptions are swallowed by design. Progress presentation is
    observational and must never change Forge execution semantics.

    Returns True when a callback was invoked successfully, otherwise False.
    """
    if not callable(on_event):
        return False

    payload = {
        'event': str(event or ''),
    }
    payload.update(fields)

    try:
        on_event(payload)
    except Exception:
        return False

    return True