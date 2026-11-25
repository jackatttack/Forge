"""Forge's run history for Anvil: stored runs found, summed up and loaded.

Role: gather · Part of: anvil/runs · Pure

Pure apart from Forge's model, so tests/smoke_history.py checks it headless
with a made-up runs folder. Forge keeps each run in
forge_home/artifacts/runs/<stamp>/ (run.json, packet.txt, bundle.txt; the
newest 100). Anvil adds no copy of its own.

    stamps()              every stored stamp, oldest first
    neighbours(stamp)     (older, newer) stamps either side of one run
    recent()              summaries for the Runs page, newest first
    load_model(stamp)     (LandingModel, items) for a stored run

Summaries come from packet.txt (small), never run.json (which keeps whole
files and can be a megabyte). Every function takes folder= for tests.
"""
import datetime
import json
import os
import re

from .page import packet_section

RUNS_LISTED = 30             # cards on the Runs page
OPS_LINE = re.compile(r'^\d+\. (\S+) \| (\S+) \|')


def runs_folder(folder=None):
    """Forge's runs folder (its own constant when Forge is importable)."""
    if folder:
        return folder
    try:
        from forge.adapters.pythonista.landing.model import RUNS_FOLDER
        return RUNS_FOLDER
    except Exception:
        return os.path.expanduser('~/.forge/artifacts/runs')


def stamps(folder=None):
    """Every stored run's stamp, oldest first (stamps sort by time)."""
    folder = runs_folder(folder)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(name for name in names
                  if os.path.isfile(os.path.join(folder, name, 'run.json')))


def neighbours(stamp, folder=None):
    """(older stamp, newer stamp) either side of stamp; None at either end."""
    known = stamps(folder)
    older = [name for name in known if name < stamp]
    newer = [name for name in known if name > stamp]
    return (older[-1] if older else None, newer[0] if newer else None)


def when(stamp):
    """'20261116_094407' -> 'Mon 16 Nov 09:44'."""
    try:
        return datetime.datetime.strptime(stamp[:15], '%Y%m%d_%H%M%S').strftime('%a %d %b %H:%M')
    except ValueError:
        return stamp


def tone_for(status):
    status = str(status).upper()
    if status.startswith('APPLIED'):
        return 'success'
    if status.startswith('SKIPPED'):
        return 'warning'
    return 'danger'


def summary(stamp, folder=None):
    """One run summed up from its packet: status, tone, op counts and
    names, changed files."""
    try:
        with open(os.path.join(runs_folder(folder), stamp, 'packet.txt'), encoding='utf-8') as handle:
            packet = handle.read()
    except OSError:
        packet = ''
    status = ''
    for line in packet.splitlines():
        if line.startswith('Status:'):
            status = line.split(':', 1)[1].strip()
            break
    ops = [OPS_LINE.match(line) for line in packet_section(packet, 'OPS').splitlines()]
    ops = [found for found in ops if found]
    counts = {'success': 0, 'warning': 0, 'danger': 0}
    for found in ops:
        counts[tone_for(found.group(1))] += 1
    if counts['danger'] or status.upper().startswith('FAILED'):
        tone = 'danger'
    elif counts['warning']:
        tone = 'warning'
    else:
        tone = 'success'
    changed = [line[2:].split(' — ')[0].strip()
               for line in packet_section(packet, 'CHANGED').splitlines() if line.startswith('- ')]
    return {'stamp': stamp, 'when': when(stamp), 'status': status, 'tone': tone,
            'counts': counts, 'op_names': [found.group(2) for found in ops], 'changed': changed}


def recent(limit=RUNS_LISTED, folder=None):
    """Summaries of the newest runs, newest first."""
    return [summary(stamp, folder) for stamp in list(reversed(stamps(folder)))[:limit]]


def load_run(stamp, folder=None):
    with open(os.path.join(runs_folder(folder), stamp, 'run.json'), encoding='utf-8') as handle:
        return json.load(handle)


def load_model(stamp, folder=None):
    """(LandingModel, items) for a stored run, with op renders' data attached,
    as the presenter builds them for a run that has just finished."""
    from forge.adapters.pythonista.landing.model import LandingModel

    from . import items as run_items
    from . import renders

    run = load_run(stamp, folder)
    model = LandingModel(run)
    renders.attach_data(model, run)
    return model, run_items.collect(run)