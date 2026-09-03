# Portable Forge for PythonIDE

The PythonIDE adapter consists of:

- `forge-entry.py` — clipboard bridge / launcher
- `forge_live_ui.py` — PythonIDE terminal presentation

The launcher executes Forge against the current PythonIDE workspace and stores
Forge state in:

    <workspace>/.forge

The canonical Forge packet remains plain text and is copied to the clipboard.
Terminal presentation is separate from protocol output.

## Terminal renderer

PythonIDE supports Rich colours and Unicode well, but its terminal does not
reliably support multi-line `rich.live.Live` repainting. Repainting a whole
live dashboard can leave historical frames in terminal scrollback.

The adapter therefore uses a terminal-native presentation strategy:

- append-only operation rows;
- one carriage-return spinner line for the active operation;
- stable progress bars after each completed operation;
- one permanent final summary;
- outcome and timing graphs;
- clipboard handoff status.

This keeps the interface animated without relying on multi-line terminal
redraw behaviour.

The renderer captures PythonIDE's current `sys.stdout` stream when it is
created. Forge's `RUN` operation may later replace the global `sys.stdout`
temporarily while capturing child-script output. Holding the original stream
keeps terminal presentation visible without inserting presentation escape
sequences into Forge's captured `RUN` output.

If Rich cannot be imported, `forge-entry.py` falls back to simple plain
progress messages.

## Launcher preamble

The normal PythonIDE interface starts directly with the Forge renderer. The
legacy clipboard-bridge preamble is hidden by default and can be enabled for
adapter debugging by setting:

    SHOW_BRIDGE_PREAMBLE = True

in `forge-entry.py`.

## Installation

The repository installer owns installation of this adapter.

Use:

    python install.py --github jackatttack/Forge --ref main \
        --pythonide-workspace /path/to/Workspace

The PythonIDE bootstrap resolves `main` to one exact commit before installing,
so the adapter and runtime come from the same repository snapshot.

Development bootstraps may also use `--force` to update an existing installation
that already carries Portable Forge installer markers.
