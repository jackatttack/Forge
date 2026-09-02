# Installing Forge

Portable Forge is intended to support several installation routes.

## Standard Python packaging

Forge is published as the normal Python distribution:

    portable-forge

Install it with:

    pip install portable-forge

The Python import is:

    import forge

## Pure Python installer

The repository includes a standard-library-only installer:

    install.py

Its purpose is to support environments where pip is unavailable or
inconvenient.

The installer can install from:

- a local checkout;
- a tagged GitHub release archive;
- an explicit archive URL.

The installer should copy only the runtime packages:

    forge/
    forge/core/
    forge/packages/

Platform adapters and documentation remain repository assets.

## Bootstrap helpers

Some environments make downloading a repository awkward.

Small bootstrap scripts can live under:

    bootstrap/

A bootstrap should only obtain and invoke install.py with suitable arguments.

The bootstrap must not become a second installer implementation.

## Pythonista

Pythonista will have a small environment-specific bootstrap and adapter.

The intended relationship is:

    Pythonista
        |
        v
    small wrapper
        |
        v
    Portable Forge

There is no Pythonista-specific fork of the core runtime.

## Release installs

The public repository is:

    jackatttack/Forge

Stable installation uses the tagged release:

    python install.py --github jackatttack/Forge --ref v0.1.1

For deliberate development testing, main remains available:

    python install.py --github jackatttack/Forge --ref main