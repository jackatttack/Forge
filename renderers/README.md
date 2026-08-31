# Forge renderers

Portable Forge deliberately starts with one plain renderer:

    forge.render_standard(run)

That returns:

    canonical Forge packet
    plus
    small human summary

This directory is reserved for richer reusable rendering experiments.

## Current extension pattern

Python imports are enough for now:

    import forge
    from my_renderer import render

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    render(run)

There is intentionally no renderer registry or plugin framework yet.

If several real environment renderers later reveal a stable shared contract,
Forge can extract that contract from working implementations.

Platform-specific renderers may also live directly inside their adapter
directory when they are not generally reusable.

The important dependency rule remains:

    renderer -> Forge

never:

    Forge -> renderer