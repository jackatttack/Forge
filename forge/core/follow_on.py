# -*- coding: utf-8 -*-
"""
Follow-on runs: fix and replay in one bundle.

A bundle may end with FORGE rerun <stamp> or FORGE resume <stamp>. The
operations before that line run first, as a run of their own. Only if that
run applies does the rerun or resume start, as a second run with its own
stamp. A repair and its replay then cost one round trip instead of two.

Why two runs and not one: Forge parses a whole bundle before executing any
of it, and the stored bundle being replayed can only be parsed after the
repair to it has landed. Running the halves in sequence keeps that promise
for each of them.

What a host sees: one outcome. The returned run joins both runs' results
and packets, and the progress events are passed on as one continuous run
(one start, operations numbered straight through, one finish), because
hosts treat the first run_finished as the end of the launch.

What is stored: two ordinary runs, exactly as if two bundles had been sent,
so DIFF, REVERT and FORGE resume keep working per run.
"""

import re

from forge.core.events import emit_event


# ----- Fixed vocabulary -------------------------------------------------

# The follow-on command: the last line of the bundle, at column 0.
_FOLLOW_ON_LINE = re.compile(r'^FORGE[ \t]+(rerun|resume)[ \t]+\S+[ \t]*$')

# Events the second run would repeat. The host has already seen them once.
_SECOND_RUN_OPENERS = ('run_started', 'parse_started', 'parse_finished')

# Appended to a packet's Repair: line, so the option is seen where it helps.
SAME_BUNDLE_NOTE = ' (alone, or as the last line of that same bundle)'


# ----- Splitting the bundle ----------------------------------------------

def split_follow_on(bundle_text):
    """Return (first_text, follow_text, follow_line), or None.

    None means the bundle has no follow-on: it does not end with a rerun
    or resume line, or that line is the whole bundle (the ordinary path).

    A valid bundle can only end with such a line at command level: inside
    a block the last line would be the block's end marker. If a block was
    left open, the first part fails to parse and the follow-on never
    starts, which is the right outcome.
    """
    from forge.core.preparse import take_env_header, unwrap_fenced_bundle

    text, bundle_app = take_env_header(bundle_text)
    fenced = unwrap_fenced_bundle(text)
    if fenced is not None:
        text = fenced[0]
        if bundle_app is None:
            text, bundle_app = take_env_header(text)

    from forge.core.parser import bundle_lines

    lines = bundle_lines(text)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines or not _FOLLOW_ON_LINE.match(lines[-1]):
        return None

    follow_line = lines[-1].strip()
    before = lines[:-1]
    if not any(line.strip() for line in before):
        return None

    # Each half keeps the ENV: header, so both packets name the same app.
    header = ('ENV: %s\n' % bundle_app) if bundle_app else ''
    first_text = header + '\n'.join(before).rstrip() + '\n'
    return first_text, header + follow_line, follow_line


# ----- One continuous run for the host -----------------------------------

class ChainedEvents(object):
    """on_event for both halves: passes them on as one continuous run."""

    def __init__(self, on_event=None):
        self.on_event = on_event
        self.following = False     # True while the second run executes
        self.offset = 0            # operations the first run reported
        self.held_finish = None    # the latest run_finished, kept back

    def __call__(self, event):
        if not isinstance(event, dict):
            return
        name = str(event.get('event') or '')

        if name == 'run_finished':
            # Never passed straight on: finish() sends the one the host sees.
            self.held_finish = dict(event)
            return

        if self.following:
            if name in _SECOND_RUN_OPENERS:
                return
            if name in ('operation_started', 'operation_finished'):
                event = dict(event)
                for key in ('index', 'total'):
                    if event.get(key) is not None:
                        event[key] = int(event[key]) + self.offset

        if callable(self.on_event):
            self.on_event(event)

    def start_follow_on(self, operations_done):
        """The first run applied; the second is about to start."""
        self.following = True
        self.offset = int(operations_done or 0)

    def finish(self, **fields):
        """Send the single run_finished.

        With no fields, the held one goes out unchanged (the follow-on
        never started). Otherwise the fields describe both runs together.
        """
        payload = dict(self.held_finish or {})
        payload.pop('event', None)
        payload.update(fields)
        emit_event(self.on_event, 'run_finished', **payload)


# ----- One returned run ---------------------------------------------------

def combine(first, second):
    """Return the run a host presents for a bundle and its follow-on.

    It is the second run (its status is the outcome) carrying both runs'
    operations, errors and packets. The stored runs are not changed.
    """
    combined = dict(second)

    combined['results'] = (
        list(first.get('results') or [])
        + list(second.get('results') or [])
    )
    combined['parsed_ops'] = (
        list(first.get('parsed_ops') or [])
        + list(second.get('parsed_ops') or [])
    )
    combined['errors'] = (
        list(first.get('errors') or [])
        + list(second.get('errors') or [])
    )

    packet = (
        str(first.get('packet') or '').rstrip('\n')
        + '\n\n'
        + str(second.get('packet') or '')
    )
    combined['packet'] = packet
    combined['packet_bytes'] = len(packet.encode('utf-8'))
    combined['chain'] = [first.get('stamp') or '', second.get('stamp') or '']
    return combined