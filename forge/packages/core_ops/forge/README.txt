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

Two built-in roots can be switched on with a feature flag instead of
writing paths:

    {"config_version": 1, "features": {"host_roots": true}}

This adds forge_home: (Forge's own home: config, runs and installed user
ops) and home: (the user's home directory; on Pythonista, the whole app
container, including Documents and Forge's home). Off by default. A root
configured under either name in "roots" replaces the built-in one.

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

## Rerun a repaired bundle

A bundle refused with FAILED_PARSE ran nothing. Forge keeps its exact text,
so a large bundle with one small mistake can be repaired in place and
replayed instead of resent.

The packet of a stored FAILED_PARSE run names the file and the command:

    Repair: REPLACE forge_home:artifacts/runs/<stamp>/bundle.txt, then FORGE rerun <stamp>

The path uses the forge_home: root when host_roots is on, and is absolute
otherwise. Repair it with an ordinary REPLACE or INSERT. When the repair
touches marker lines themselves, such as a missing END_BODY, tag the
edit's own blocks so those markers are plain text:

    REPLACE forge_home:artifacts/runs/<stamp>/bundle.txt
    BEGIN_OLD @fix
    hello

    READ app.py
    END_OLD @fix
    BEGIN_NEW @fix
    hello
    END_BODY

    READ app.py
    END_NEW @fix

Then replay it, as the whole bundle:

    FORGE rerun <stamp>

The replay is a new run with its own stamp, and its packet shows
`Rerun of: <stamp>`.

- FORGE rerun must be the only line of its bundle; an ENV: line is fine.
- Only FAILED_PARSE runs replay, because they ran nothing. A partly
  applied run is carried on with FORGE resume instead (below).
- If the replay fails to parse again, repair the original run's bundle and
  rerun the original stamp. A rerun of a rerun is refused and names the
  original.
- Repairing edits the stored record of the failed run, which is safe
  because that run changed nothing.

## Resume a partly applied run

A bundle that fails part-way leaves its earlier operations applied and its
later ones skipped. Its packet names the way to carry on:

    Resume: FORGE resume <stamp> carries on at op 16 of 23 (DELETE app.py); to change an op first, REPLACE forge_home:artifacts/runs/<stamp>/bundle.txt

Fix the cause first. If the failing operation itself was wrong (an OLD block
that did not match), repair it in the stored bundle named on that line. If
the bundle was right and the project was wrong (a failing test behind
STOP_ON_FAIL), fix the project with an ordinary bundle. Then send, as the
whole bundle:

    FORGE resume <stamp>

The operations that already applied are not run again; everything from the
first one that did not apply runs. The resumed run is a new run whose packet
shows `Resume of: <stamp>` and still lists every operation of the bundle.

- FORGE resume must be the only line of its bundle; an ENV: line is fine.
- Only a FAILED run with one place to carry on from can resume: after its
  first operation that did not apply, only read-only operations applied.
  The Resume: line appears only on runs that qualify.
- The operations that already applied must be unchanged in the stored
  bundle. Edit only the failing operation and those after it.
- A pin (IF_VERSION) on a file an applied operation already changed still
  passes, as long as nothing else has touched that file since.
- If the resumed run fails again, resume that run's stamp.
- A FAILED_PARSE run ran nothing: use FORGE rerun for it.
- REVERT works per run: the original run and each resumed run are
  reverted separately, newest first.

## Limits

FORGE does not change project files or configuration. FORGE rerun and
FORGE resume replay a stored bundle as a new run; the replayed operations
make the changes.

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

When a large bundle fails to parse over a small mistake, repair the stored
bundle named on the packet's Repair: line and send FORGE rerun <stamp>,
rather than resending the whole bundle.

When a bundle fails part-way (Status: FAILED with skipped operations), the
packet's Resume: line names the command. Fix the cause, then send FORGE
resume <stamp> rather than rewriting the remaining operations by hand.