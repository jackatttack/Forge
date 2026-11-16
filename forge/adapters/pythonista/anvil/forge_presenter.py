# -*- coding: utf-8 -*-
"""Forge's presenter: forge.json names this module to show runs in Anvil.

    {"config_version": 1, "presenter": "anvil.forge_presenter"}

make_listener(renderer) is called once when a run is launched. It wraps
Forge's (quiet) console renderer in Forge's own LandingListener, whose
LiveRun records each event as plain data behind a lock; its dock call is
Anvil's start_live, so Anvil opens when the run starts and fills in as ops
finish. show_after_run(run, progress) is called once the packet is on the
clipboard and swaps in the finished run.

Returning False, or raising, hands the run to Forge's built-in landing
(forge/adapters/pythonista/presenter.py keeps the reason in last_error),
so Anvil can never cost a run its result.
"""


def make_listener(renderer=None):
    """The run's on_event: Forge's renderer, a live record, Anvil at start."""
    from forge.adapters.pythonista.landing.live import LandingListener

    from . import landing
    return LandingListener(renderer, dock=landing.start_live)


def show_after_run(run, progress=None):
    """Show the finished run in Anvil. True when shown."""
    from forge.adapters.pythonista.landing.hook import has_console_output
    from forge.adapters.pythonista.landing.model import LandingModel

    from . import landing

    # An op that printed to the console (MATH and friends) must stay
    # visible. Until Anvil can show that output itself, Anvil folds away and
    # the built-in landing docks collapsed for such runs. Known gap: EDITOR
    # items in such a run are listed in the packet but not shown.
    if has_console_output(run):
        landing.step_aside()
        return False

    from . import items as run_items
    from . import renders

    model = LandingModel(run,
                         timings=getattr(progress, 'timings', None),
                         run_elapsed=getattr(progress, 'run_elapsed', None))
    renders.attach_data(model, run)          # op renders read each result's data
    return landing.show_run(model, run_items.collect(run))