"""Forge Landing for the Pythonista launcher.

adapters/pythonista/Forge.py uses two entry points:
    make_listener(renderer)      the on_event for forge.run_text; docks the
                                 landing when the run starts and fills it live
    show_after_run(run, progress) after the final summary and clipboard
                                 status: finishes the live landing, or docks
                                 a complete one when none is docked
Presentation only: never raises, never changes the run or the clipboard
packet. If the landing cannot load or dock, the console's text summary stays.
"""


def has_console_output(run):
    """True when an op handed over console output (result data 'console').

    The landing must not cover that output, so it then docks collapsed.
    """
    for result in (run or {}).get('results') or []:
        data = result.get('data') if isinstance(result, dict) else None
        if isinstance(data, dict) and data.get('console'):
            return True
    return False


def make_listener(renderer=None):
    """Wrap Forge's console renderer so the landing docks live at run start."""
    from .live import LandingListener
    from .panel import show_live_landing
    return LandingListener(renderer, dock=show_live_landing)


def show_after_run(run, progress=None):
    """Finish or dock the landing for this finished run. True when shown."""
    try:
        from .model import LandingModel
        from .panel import finish_live_landing, show_landing
        model = LandingModel(run,
                             timings=getattr(progress, 'timings', None),
                             run_elapsed=getattr(progress, 'run_elapsed', None))
        collapsed = has_console_output(run)
        if getattr(progress, 'docked', False) and finish_live_landing(model, collapsed=collapsed):
            return True
        return bool(show_landing(model, collapsed=collapsed))
    except Exception:
        return False