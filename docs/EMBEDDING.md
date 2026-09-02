# Embedding Forge

Forge can be called directly from another Python program.

## Smallest useful example

    import forge

    run = forge.run_text(
        bundle,
        project_root="/path/to/project",
    )

    print(
        forge.render_standard(run)
    )

## Public API

The intended public surface is small:

    forge.run_text(...)
    forge.render_standard(...)
    forge.make_environment(...)
    forge.standard_environment(...)
    forge.first_boot_text()

Most applications should not need to import forge.core directly.

## Explicit environments

Specialised hosts can resolve runtime paths themselves:

    import forge

    environment = forge.make_environment(
        project_root="/project",
        forge_home="/state/forge",
        storage_root="/state/forge/artifacts",
        aliases_path="/state/forge/aliases.json",
        host="my-host",
        capabilities={},
    )

    run = forge.run_text(
        bundle,
        environment=environment,
    )

Portable core receives these facts.

It does not perform host detection itself.

## Rendering

run["packet"] is canonical.

forge.render_standard(run) returns the canonical packet followed by the small
standard human summary.

A host can consume the structured run directly when it wants richer
presentation.