# Pythonista adapter

Portable Forge itself has no Pythonista dependency.

Pythonista is simply one environment that wraps the importable Forge runtime.


## Installation shape

On Pythonista, the intended layout is:

    ~/Documents/site-packages-3/
        forge/
        forge_core/
        forge_packages/

    ~/Documents/forge_entry.py

The Forge runtime lives in `site-packages-3`.

`forge_entry.py` is only the small Pythonista-specific host launcher.


## Bootstrap

The repository includes:

    bootstrap/pythonista.py

Running that bootstrap on a clean Pythonista installation will:

1. Download the Portable Forge installer.
2. Install `forge`, `forge_core`, and `forge_packages` into
   `~/Documents/site-packages-3`.
3. Create `~/Documents/forge_entry.py`.
4. Open `forge_entry.py` in the Pythonista editor.

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
    forge_core
    forge_packages

An older Forge installation may already use one or more of the same names.

The installer therefore checks for namespace collisions and refuses to
silently shadow or overwrite an existing runtime.

Migration should be deliberate.


## Richer Pythonista rendering

A richer Pythonista renderer can later live beside the root launcher:

    renderer.py

The launcher could then do:

    import forge
    from renderer import render

    run = forge.run_text(...)
    render(run)

That renderer remains a Pythonista concern.

The dependency direction must stay:

    Pythonista adapter -> Forge

never:

    Forge -> Pythonista adapter