# Forge safety model

Forge is designed for human-in-the-loop local execution.

It cannot make every generated instruction risk-free, but it can make the
execution boundary explicit, inspectable, and recoverable.

## Human approval is part of the design

The assistant proposes a visible text bundle.

The user decides whether to run it.

Forge does not treat generated instructions as background authority.

## Parse first

The complete bundle is parsed before operations execute.

A parse failure prevents the operation stream from beginning.

This also creates a simple rule:

New Forge syntax created by one run is only available to a later run.

## Explicit project root

Project paths resolve against an explicit project root.

Portable core does not silently choose a working directory when required
context is missing.

## Installed code and writable state are separate

The Forge package can be treated as read-only.

Writable state such as run history, aliases, branches, and configuration lives
under a separate Forge home.

The standard host normally uses:

    ~/.forge

## Path safety

File operations check that resolved project paths remain within the project
boundary unless an operation explicitly defines another safe location.

## Checked Python writes

Where applicable, Python modifications are compile-checked before replacing
the original file.

A failed compile should fail the edit instead of silently leaving broken
source.

## Recovery

Forge stores mutation information for retained runs.

REVERT checks all target states and recovery snapshots before changing files.
It refuses newer contents, unexpected existence or file types, symlinks, and
records missing explicit existence metadata. Successful recovery changes are
tracked, so a stored REVERT run can itself be reverted.

Recovery stops on an execution error and reports any completed changes. It is
not a multi-file transaction or crash-safe journal. Run storage still happens
after execution; interruption before storage can lose recovery information.

Useful recovery operations include:

    DIFF
    REVERT
    BRANCH

## Failures are useful evidence

A failed Forge run is still useful.

Read:

- run status;
- errors;
- operation statuses;
- hints;
- previews.

Do not assume that retrying the same intent with a larger edit is safer.

## Host adapters

Host adapters live outside portable core.

A richer platform integration must not bypass the core safety model merely
because it has additional access to the environment.