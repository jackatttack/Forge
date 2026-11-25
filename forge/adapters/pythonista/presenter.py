"""
Optional presenter for the Pythonista launcher.

Role: run · Part of: forge/adapters/pythonista

forge.json may name a presenter: a module that shows a finished run in
place of the built-in Forge Landing.

    {"config_version": 1, "presenter": "my_package.forge_presenter"}

A presenter module offers:

    show_after_run(run, progress)   required. Show the finished run and
                                    return True. Return False (or raise) to
                                    hand the run to the built-in landing.
    make_listener(renderer)         optional. Return the on_event listener
                                    for the run, wrapping Forge's console
                                    renderer. It must pass the renderer's
                                    attributes through (print_clipboard_status,
                                    timings, run_elapsed), as the landing's
                                    LandingListener does.

Without make_listener the run shows Forge's live console and the presenter
is called once, after the run.

With no presenter set, Forge uses Anvil, the run view that ships with it
(forge.adapters.pythonista.anvil), when editorkit and its Toolbox
(editorkit_toolbox) are installed, and the built-in landing otherwise.
Set "presenter": "builtin" to keep the built-in landing either way.

Rules:
- Presentation only. Nothing here raises, changes the run or touches the
  clipboard packet.
- Every failure falls back to the built-in landing. The reason is kept in
  last_error, because nothing is printed.
- The presenter is chosen once per launch, when the listener is built, and
  the same choice is used after the run. A bundle that edits forge.json
  mid-run therefore cannot leave two landings on screen.
"""

import importlib
import importlib.util
import traceback

from forge.core.config import load_config


# The presenter module chosen for this launch by make_listener, or None.
_chosen = None

# Why the last presenter was not used: '' or a message with a traceback.
last_error = ''

# The forge.json presenter value that keeps the built-in landing.
BUILTIN = 'builtin'

# The run view that ships with Forge, and the libraries it needs.
BUNDLED = 'forge.adapters.pythonista.anvil.forge_presenter'
BUNDLED_NEEDS = ('editorkit', 'editorkit_toolbox')


def _note_error(message):
    """Record a failure, with the active traceback, in last_error."""
    global last_error
    last_error = '%s\n%s' % (message, traceback.format_exc())


def configured_name(forge_home=None):
    """
    Return forge.json's presenter module name, or '' when none is set.

    Never raises: an unreadable or invalid config means no presenter here.
    Reporting a bad config is the run's job, not presentation's.
    """
    try:
        if forge_home is None:
            from forge.standard import default_forge_home
            forge_home = default_forge_home()
        config = load_config(forge_home)
        return str(config.get('presenter') or '').strip()
    except Exception:
        return ''


def bundled_name(finder=None):
    """
    Return the bundled Anvil presenter's name when the libraries it needs
    are installed, else ''.

    Only looks for them (importlib.util.find_spec); nothing is imported
    unless Anvil is then chosen. finder exists for tests. Never raises.
    """
    finder = finder or importlib.util.find_spec
    try:
        if all(finder(name) is not None for name in BUNDLED_NEEDS):
            return BUNDLED
    except Exception:
        pass
    return ''


def load(name=None, forge_home=None, importer=None, finder=None):
    """
    Import the presenter and return its module, or None.

    name is read from forge.json when not given; with nothing set there,
    the bundled Anvil is chosen when its libraries are installed. 'builtin'
    means the built-in landing. importer and finder exist for tests; they
    default to importlib.import_module and importlib.util.find_spec.
    """
    global last_error
    last_error = ''

    if name is None:
        name = configured_name(forge_home) or bundled_name(finder)
    if not name or name == BUILTIN:
        return None

    try:
        module = (importer or importlib.import_module)(name)
    except Exception:
        _note_error('presenter %r could not be imported' % name)
        return None

    if not callable(getattr(module, 'show_after_run', None)):
        last_error = 'presenter %r has no show_after_run(run, progress)' % name
        return None

    return module


def make_listener(renderer_class, name=None, forge_home=None, importer=None, finder=None):
    """
    Return the run's on_event listener when a presenter is set, else None.

    None tells the launcher to use the built-in Forge Landing. renderer_class
    is Forge's console renderer (ForgeConsoleUI): it is built quiet
    (live=False) for a presenter with its own listener, and live otherwise.
    """
    global _chosen
    _chosen = None

    module = load(name=name, forge_home=forge_home, importer=importer, finder=finder)
    if module is None:
        return None

    own_listener = getattr(module, 'make_listener', None)
    if not callable(own_listener):
        _chosen = module
        return renderer_class()

    try:
        listener = own_listener(renderer_class(live=False))
    except Exception:
        _note_error('presenter make_listener failed')
        return None

    if listener is None:
        global last_error
        last_error = 'presenter make_listener returned nothing'
        return None

    _chosen = module
    return listener


def show_after_run(run, progress=None, builtin=None):
    """
    Show the finished run. True when something showed it. Never raises.

    The presenter chosen by make_listener goes first. If there is none, or
    it fails or returns False, the built-in landing shows the run. builtin
    exists for tests; it defaults to the landing's show_after_run.
    """
    global _chosen, last_error
    module = _chosen
    _chosen = None

    if module is not None:
        try:
            if module.show_after_run(run, progress):
                return True
            last_error = 'presenter did not show the run'
        except Exception:
            _note_error('presenter show_after_run failed')

    try:
        if builtin is None:
            from forge.adapters.pythonista.landing.hook import (
                show_after_run as builtin,
            )
        return bool(builtin(run, progress))
    except Exception:
        return False