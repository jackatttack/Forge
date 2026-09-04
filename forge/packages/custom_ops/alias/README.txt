# ALIAS

## Summary

ALIAS manages local Forge command shortcuts.

Aliases are stored in:

    <forge_home>/aliases.json

Use `FORGE config` to inspect the resolved Forge home and alias path. Standard
installations use a `.forge` home, commonly displayed as
`.forge/aliases.json`.

Alias expansion happens before normal bundle parsing. An alias can therefore
expand one submitted line into a complete multi-operation Forge bundle.

## Commands

List every alias:

    ALIAS list

List aliases carrying one tag:

    ALIAS list forge

List tags and their alias counts:

    ALIAS tags

Inspect one alias:

    ALIAS show boot

Add or replace an alias:

    ALIAS add boot : forge
    DESCRIPTION: Daily Forge boot bundle
    HINTS: files ops memory
    BEGIN_BODY
    MAP .
    DEPTH: 2

    FORGE ops
    END_BODY

Remove one alias:

    ALIAS remove boot

The optional text after ` : ` is the alias tag.

## Directives

- `DESCRIPTION` stores human-readable text shown by `ALIAS show`.
- `HINTS` stores space-separated descriptive labels shown by `ALIAS list` and
  `ALIAS show`. Hints do not change expansion behaviour.

The subcommand and alias name are written on the `ALIAS` line. `ARGS` is
internal parser plumbing for that same-line text.

## Parameterised aliases

Stored expansion bodies may use:

    $1      first positional argument
    $2      second positional argument
    $*      all arguments
    $-1     final argument
    $^      all arguments except the final argument

For example:

    ALIAS add readproj : files
    DESCRIPTION: Read one project's control file
    HINTS: files project
    BEGIN_BODY
    READ projects/$1/PROJECT_CONTROL.txt
    END_BODY

A later one-line submission:

    readproj tilekit

expands to:

    READ projects/tilekit/PROJECT_CONTROL.txt

If an expansion contains positional placeholders, invoking it without the
required arguments fails rather than guessing.

## Clipboard workflow

When the user-owned `CLIPBOARD` extension is installed, an alias can expose a
stored prompt as a one-line shortcut:

    ALIAS add prompt : clipboard
    DESCRIPTION: Copy a named prompt
    HINTS: clipboard prompts
    BEGIN_BODY
    CLIPBOARD prompts/$1.txt
    END_BODY

Then:

    prompt review

expands to `CLIPBOARD prompts/review.txt`.

## Limits and safety

Aliases only expand when the submitted bundle contains one non-empty line.
They are command shortcuts, not macros embedded inside ordinary bundles.

Real Forge operation names always win. ALIAS refuses new names that collide
with currently discovered operations.

Alias names are case-sensitive; lowercase names are recommended.

Aliases are trusted local workflow configuration. Inspect an unfamiliar alias
with `ALIAS show <name>` before running it.