# ALIAS

ALIAS manages local Forge command shortcuts.

Aliases are stored as JSON in:

    forge/aliases.json

Alias expansion is handled by Forge's pre-parser before normal bundle parsing. This package provides the management surface for listing, showing, adding, and removing aliases.

## Commands

    ALIAS list

    ALIAS list forge

    ALIAS tags

    ALIAS show boot

    ALIAS add boot : forge
    DESCRIPTION: Daily Forge boot bundle
    HINTS: files ops memory
    BEGIN_BODY
        MAP .
        DEPTH: 2

        FORGE ops

        MEMORY boot
    END_BODY

    ALIAS remove boot

## Expansion placeholders

Stored expansion bodies may use:

    $1      first positional argument
    $2      second positional argument
    $*      all arguments
    $-1     final argument
    $^      all arguments except final argument

These placeholders are expanded when a one-line submitted bundle matches an alias name.

## Notes

Real Forge op names should not be shadowed by aliases. ALIAS refuses names that collide with currently discovered op names.

Alias names are case-sensitive, but lowercase names are recommended.