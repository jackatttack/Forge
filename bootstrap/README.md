# Forge bootstrap helpers

Bootstrap helpers are for Python environments where obtaining or installing a
full repository is inconvenient.

A bootstrap should remain very small.

Its job is:

    obtain install.py
            |
            v
    run install.py with suitable arguments

The repository-root install.py remains the one authoritative installer.

A bootstrap must not grow into a second installer implementation.

## Pythonista

The initial bootstrap template is:

    pythonista.py

The Pythonista bootstrap uses:

    REPOSITORY = jackatttack/Forge
    REF = v0.1.1

Stable bootstrap releases are pinned to a tag rather than main so installation
remains reproducible after later development changes.

## PythonIDE

The development bootstrap is:

    pythonide.py

PythonIDE development installs currently use:

    REPOSITORY = jackatttack/Forge
    REF = main

This deliberately tracks the GitHub development branch so Forge changes can be
tested in PythonIDE without waiting for a new PyPI release. The bootstrap only
downloads and launches the repository-root install.py; it does not duplicate
installer logic.

For the cleanest development setup, remove any existing PyPI-installed Portable
Forge runtime before using this bootstrap.