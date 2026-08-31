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

Before the public repository is created, it contains placeholder repository
coordinates.

After the repository exists, set:

    REPOSITORY
    REF

to the real GitHub repository and a known release tag.

Stable instructions should prefer a tagged release rather than main.