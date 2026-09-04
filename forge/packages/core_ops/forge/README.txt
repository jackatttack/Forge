FORGE
=====

FORGE is the read-only entry point for understanding Forge itself.

Use it to discover operations, learn bundle syntax, inspect configuration,
check package health, and recover stored run information.

## Which help do I want?

Quick orientation:

    FORGE help WRITE

This shows the operation's purpose, a compact example, and its public
directives.

Complete reference:

    FORGE help WRITE full

This shows the operation's full guide, worked examples, limits, public
directives, and parser contract.

Package health:

    FORGE help WRITE contract

This checks whether the installed operation package is structurally sound and
whether its structured directive documentation agrees with its parser
contract. It is a health check, not usage documentation.

## After a parse failure

Read the returned parser error first.

If the overall bundle grammar is unclear, use:

    FORGE bundle

If one operation's syntax or directives are unclear, use:

    FORGE help <OP> full

`FORGE bundle` explains command-level lines, directives, body blocks, and why
the complete bundle must parse before any operation executes.

## Discover operations

List the stable public language:

    FORGE ops

Include installed local extensions:

    FORGE ops all

Use `ops all` only when an extension is relevant. The public list is the normal
starting point.

## First-boot orientation

    FORGE boot

This returns Forge's portable first-boot guide: the clipboard loop, inspection
order, recovery model, and standard working style.

## Bundle syntax

    FORGE bundle

This returns the grammar understood by the currently installed parser.

A complete copied bundle may optionally be wrapped in one Markdown fence using
no label, `forge`, `text`, or `plaintext`. Forge unwraps only the whole
submission; it never searches surrounding chat prose for executable content.

## Health

Check every installed operation package:

    FORGE audit

The audit reports missing package resources, invalid manifests, broken SPEC or
HELP metadata, and structured directive-documentation drift.

## Runtime configuration

    FORGE config

This shows the resolved project root, Forge home, artifact storage, alias
registry, and host environment. It never prints credentials.

## Stored runs

List the ten most recent runs in the current Forge mode:

    FORGE runs

Choose another maximum:

    FORGE runs
    LIMIT: 25

Inspect the newest stored packet:

    FORGE runs latest

Inspect one artifact from a known run:

    FORGE runs show <stamp>
    FORGE runs show <stamp> packet
    FORGE runs show <stamp> surface
    FORGE runs show <stamp> bundle
    FORGE runs show <stamp> json

`latest` returns the newest packet and any stored human-facing surface.
`show` requires an explicit run stamp.

## Limits

FORGE does not change project files or configuration.

`FORGE help <OP> contract` checks package structure and structured help
metadata. It does not prove that every prose sentence or example is correct.

Run history is mode-specific. A development run lists development history, not
history stored under another Forge mode.

## Notes for LLMs

Use quick help for orientation and full help before writing unfamiliar syntax.

Do not use contract mode to infer operation behaviour; it answers whether the
package is healthy, not how the operation works.

After `FAILED_PARSE`, prefer the exact parser error, `FORGE bundle`, and the
relevant operation help over guessed directives.