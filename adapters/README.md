# Forge adapters

Adapters connect Portable Forge to a specific environment.

The rule is simple:

    Adapters import Forge.
    Forge never imports adapters.

An adapter may provide:

- bundle input;
- project-root selection;
- clipboard access;
- editor integration;
- richer presentation;
- UI controls;
- environment capabilities.

The portable runtime remains unchanged.

Current adapter:

    pythonista/

Future environments can be added as siblings rather than branching or
special-casing the Forge core.