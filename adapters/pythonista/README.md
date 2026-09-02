# Pythonista adapter

Portable Forge itself has no Pythonista dependency.

Pythonista is simply one environment that wraps the importable Forge runtime.


## Installation shape

On Pythonista, the intended layout is:

    ~/Documents/site-packages-3/
        forge/
            core/
            packages/
            adapters/
                pythonista/
                    console_ui.py

    ~/Documents/forge_entry.py

The Forge runtime and supported Pythonista console adapter live beneath the
single `forge` package in `site-packages-3`.

`forge_entry.py` is the small Pythonista-specific host launcher.


## Bootstrap

The repository includes:

    bootstrap/pythonista.py

Running that bootstrap on Pythonista will:

1. Download the current Portable Forge installer from `main`.
2. Install the single `forge` package, including `forge.core`,
   `forge.packages`, and `forge.adapters.pythonista`, into
   `~/Documents/site-packages-3`.
3. Install `~/Documents/forge_entry.py`.
4. On first installation, open `forge_entry.py` in the Pythonista editor.

Marked Portable Forge adapter files can be safely refreshed on later bootstrap
runs.

The installer owns the Pythonista-specific finishing work. The bootstrap only
downloads and invokes the installer.

After installation, Forge can also be imported normally:

    import forge


## The launcher source

The repository keeps the launcher template at:

    adapters/pythonista/Forge.py

During Pythonista installation that template is copied to:

    ~/Documents/forge_entry.py

The different installed filename avoids placing a root-level `Forge.py` beside
the importable `forge` package while keeping the adapter source easy to
recognise inside the repository.


## Clipboard loop

The launcher implements a deliberately small host loop:

    clipboard
        |
        v
    get_bundle_text()
        |
        v
    forge.run_text(...)
        |
        v
    forge.render_standard(...)
        |
        v
    set_result_text()
        |
        v
    clipboard

The important part is not the clipboard.

The important part is that Portable Forge is just an import. The environment
decides how bundle text enters the loop and where the result goes.


## Customising the loop

`forge_entry.py` keeps the host-specific behaviour obvious.

The two main edges are:

    get_bundle_text()

and:

    set_result_text(text)

A Pythonista host could replace clipboard input with:

- a text file;
- an editor buffer;
- a UI text box;
- generated text;
- another local service.

Output could similarly go to:

- clipboard;
- console;
- a file;
- a custom UI.

None of those choices require changing Portable Forge.


## Project root

The supplied Pythonista launcher defaults to:

    ~/Documents

Change `PROJECT_ROOT` if Forge should operate against a narrower project
directory.


## Existing Forge installations

Portable Forge uses these import namespaces:

    forge
    forge.core
    forge.packages

An older Forge installation may already use one or more of the same names.

The installer therefore checks for namespace collisions and refuses to
silently shadow or overwrite an existing runtime.

Migration should be deliberate.


## Pythonista live rendering

The supported Pythonista console adapter is packaged at:

    forge.adapters.pythonista.console_ui

`forge_entry.py` imports `ForgeConsoleUI` from that packaged adapter and passes
it to:

    forge.run_text(..., on_event=progress)

The adapter consumes Portable Forge's structured execution events and draws
the live Pythonista console presentation. The canonical standard packet is
still rendered separately and copied to the clipboard.

There is no separate root-level renderer in new installations.

Presentation remains host-side. The dependency direction is:

    forge.adapters.pythonista -> Forge public API -> forge.core

The portable core does not depend on the Pythonista adapter.