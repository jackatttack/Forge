# Portable Forge for PythonIDE

The PythonIDE adapter consists of:

- `forge-entry.py` — clipboard bridge / launcher
- `forge_live_ui.py` — optional Rich live execution dashboard

The launcher executes Forge against the current PythonIDE workspace and stores
Forge state in:

    <workspace>/.forge

The canonical Forge packet remains plain text and is copied to the clipboard.
Terminal presentation is separate from protocol output.

## Rich dashboard

PythonIDE currently provides Rich, so `forge_live_ui.py` displays:

- parse state
- operation progress
- current operation
- completed operation history
- elapsed timings
- final run status

If Rich cannot be imported, `forge-entry.py` falls back to simple plain progress
messages.

A deliberate implementation detail is that the dashboard captures PythonIDE's
current `sys.stdout` stream when it is created. Forge's RUN operation may later
replace the global `sys.stdout` temporarily while capturing child-script output.
Holding the original stream keeps the dashboard visible without inserting Rich
terminal escape sequences into Forge's RUN output.

## Installation

The repository installer owns installation of this adapter.

Use:

    python install.py --github jackatttack/Forge --ref main \
        --pythonide-workspace /path/to/Workspace

Development bootstraps may also use `--force` to update an existing installation
that already carries Portable Forge installer markers.