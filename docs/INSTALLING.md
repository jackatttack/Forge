# Installing Forge

Portable Forge is intended to support several installation routes.

## Standard Python packaging

The repository includes pyproject.toml so Forge can eventually be installed as
a normal Python distribution.

The final public distribution name should be confirmed before the first PyPI
upload.

The Python import will remain:

    import forge

## Pure Python installer

The repository will include a standard-library-only installer:

    install.py

Its purpose is to support environments where pip is unavailable or
inconvenient.

The installer will be able to install from:

- a local checkout;
- a tagged GitHub release archive;
- an explicit archive URL.

The installer should copy only the runtime packages:

    forge/
    forge_core/
    forge_packages/

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

During development, installation can use:

    python install.py --github jackatttack/Forge --ref main

Stable installation instructions should prefer a tagged release once the
first release tag exists, for example:

    python install.py --github jackatttack/Forge --ref v0.1.0