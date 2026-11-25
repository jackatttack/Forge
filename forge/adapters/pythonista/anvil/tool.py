"""Anvil as a Toolbox tool: open the latest stored Forge run.

Role: run · Part of: anvil/toolbox

Toolbox/tools/forge.json names this module and main (written by
projects/anvil/tools/install.py).
"""
import os


def stored_packet(stamp):
    """The packet Forge stored for a run (packet.txt), or ''."""
    from . import items as run_items

    path = os.path.join(run_items.RUNS_FOLDER, str(stamp), 'packet.txt')
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return handle.read()
    except OSError:
        return ''


def main():
    """Show the most recent stored run, with its items and saved answers."""
    from forge.adapters.pythonista.landing.model import LandingModel, load_stored_run

    from . import items as run_items
    from . import landing

    run = load_stored_run()
    if not run.get('packet'):
        run['packet'] = stored_packet(run.get('stamp'))
    return landing.show_run(LandingModel(run), run_items.collect(run))