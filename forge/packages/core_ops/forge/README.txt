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

Under each op's summary, the list shows its directives and body shape,
generated from the op itself so they always match what the parser accepts,
and, where the op provides one, a one-line brief of its limits and most
useful capabilities. That is usually enough to write a bundle without a
help call; use `FORGE help <OP>` for syntax details and examples.

Include installed local extensions:

    FORGE ops all

Use `ops all` only when an extension is relevant. The public list is the normal
starting point.

## First-boot orientation

    FORGE boot

This returns a compact portable first-boot guide: essential operating rules
and pointers to focused workflow documentation.

## Workflow documentation

Browse the small catalogue:

    FORGE docs

Read one guide:

    FORGE docs edit

Find guidance when its name is unknown:

    FORGE search docs undo a change

Search returns at most three relevance-ranked guides with summaries and
retrieval commands. Exact guide names and titles rank first. Queries are
plain text, limited to 240 characters; LIMIT applies only to stored runs.

Available guides cover inspection, editing, recovery, workflow and human-owned
code. They ship with the installed Forge version and work offline, without
MEMORY or other local extensions. Search creates no disk cache.

These guides explain decisions and cross-operation workflows. Operation syntax
remains in FORGE help <OP>; bundle grammar remains in FORGE bundle.

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
registry, host environment, and any configured named roots. It never prints
credentials.

## Named roots

By default every path in a bundle resolves against the project root.

A Forge home may configure additional named roots in forge.json:

    {
      "config_version": 1,
      "roots": {
        "icloud": "/absolute/path/to/another/tree"
      }
    }

A path then opts in to one of those roots with a "name:" prefix:

    READ icloud:tools/patcher.py

    COPY icloud:tools/patcher.py
    TO: projects/example/patcher.py

Paths without a prefix are unaffected and still resolve against the project
root, so existing bundles keep working exactly as before.

A root name cannot contain ":" or a path separator. An unknown prefix fails
the operation rather than silently falling back to the project root.

`FORGE config` lists each configured root with its resolved path and whether
it is currently reachable, which is worth checking before working against one.

Recovery records which root each changed file belonged to, so REVERT restores
into the correct tree.

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