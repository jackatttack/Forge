FORGE
=====

FORGE is Forge's self-inspection and control-plane verb.

It provides Forge self-inspection, help, health checks, configuration, and stored run history.

Public language:

    FORGE
    FORGE ops

First-boot orientation:

    FORGE boot

`FORGE boot` returns the same canonical portable guide exposed by
`forge.first_boot_text()` and `python -m forge --first-boot`.

Bundle syntax:

    FORGE bundle

`FORGE bundle` returns the command-language grammar: what a bundle may
contain at command level, how blocks work, and what causes a parse
failure. It is exposed the same three ways, through
`forge.bundle_syntax_text()` and `python -m forge --bundle-syntax`.

Use `FORGE boot` to learn the loop. Use `FORGE bundle` to learn the
syntax. Use `FORGE help <OP>` to learn one operation.

All installed powers:

    FORGE ops all

Help:

    FORGE help WRITE
    FORGE help WRITE full
    FORGE help WRITE contract

Health:

    FORGE audit

Runtime configuration/context:

    FORGE config

Stored run history:

    FORGE runs
    FORGE runs latest
    FORGE runs show <stamp>
    FORGE runs show <stamp> packet
    FORGE runs show <stamp> bundle
    FORGE runs show <stamp> json

FORGE is read-only in this milestone.