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
    REF = v0.1.0

Stable bootstrap releases are pinned to a tag rather than main so installation
remains reproducible after later development changes.