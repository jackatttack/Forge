# Host adapters

A host adapter connects Portable Forge to one concrete environment.

The architectural rule is:

Adapters import Forge. Forge never imports adapters.

## Responsibilities

A host may decide:

1. Where bundle text comes from.
2. What the project root is.
3. Where writable Forge state lives.
4. What optional host capabilities exist.
5. Where the result is sent.
6. How a structured run is presented.

## Minimal shape

    import forge

    bundle = get_bundle_from_host()

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    output = forge.render_standard(run)

    send_output_to_host(output)

## What an adapter should not do

An adapter should not:

- reimplement the Forge parser;
- redefine operation semantics;
- mutate the canonical packet;
- maintain a second run-history format;
- bypass core safety checks.

## Platform-specific rendering

A richer host can render the structured run directly:

    import forge
    from my_platform_renderer import render

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    render(run)

There is intentionally no renderer registry yet.

Python imports already provide a simple extension mechanism.

If several real renderers later reveal a stable common contract, Forge can
extract one from those working implementations.