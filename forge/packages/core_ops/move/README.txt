# MOVE

## Summary

MOVE moves one file or a whole directory tree to a new path. Either path may
use a named root such as icloud:, so moves work between roots in both
directions.

MOVE shares COPY's planning: it checks everything first and refuses the
whole move before changing anything if there is a problem. It then copies
every file, verifies each copy against its source, and only after every
copy checks out removes the source files and any source directories left
empty.

## Move a file

    MOVE scratch/old_name.py
    TO: scratch/new_name.py

## Move a directory

    MOVE icloud:projects/old_game/game
    TO: icloud:projects/maths_games/games/multiple_merge

TO names the destination itself, never a folder to move into.

## Filters leave files behind

GLOB and EXCLUDE work as in COPY. Files they skip stay at the source, so
the directories holding them are not removed. The defaults skip
__pycache__, *.pyc, .DS_Store and script_snapshots; EXCLUDE: none switches
them off.

## Existing destination files

OVERWRITE works as in COPY: no (default) refuses when an existing file
differs, yes replaces differing files, and replace also removes destination
files the source lacks.

## Preview first

    MOVE projects/big_folder
    TO: icloud:projects/big_folder
    DRY_RUN: yes

## Limits and confirmation

A move that would change more than 200 files needs CONFIRM: yes, as does a
move that changes protected core paths. A move counts both the destination
writes and the source removals.

## Recovery

Every destination file and every removed source file is recorded. REVERT
restores the sources, recreating any directories MOVE removed, and deletes
the copies. Destination folders MOVE created are left behind, empty.

If the move stops part-way, every change made before it is recorded, and
REVERT undoes the partial move. Sources are never removed until every copy
has been verified.

Binary files are supported automatically, with no extra directive.
Files are moved byte-for-byte, including original text line endings.
Binary and large files use chunked I/O and file-backed recovery snapshots;
DIFF shows their byte counts and SHA-256 checksums.

Destination writes are staged and verified before atomic replacement.
Before any source is removed, MOVE checks every destination and every
current source against the planned snapshots. It also rechecks the source
and its copy immediately before each removal. Observable changes stop the
move, preserving the changed source.

These checks do not lock out concurrent writers. Completed changes rely on
normal end-of-bundle run storage; the whole move is not crash-atomic.
REVERT refuses newer edits and damaged snapshots, and is itself reversible.
DRY_RUN may create temporary snapshots but changes no source or destination.

## Directives

- `TO: path` — required destination path itself.
- `OVERWRITE: no|yes|replace` — policy for existing destination files.
- `GLOB: patterns` — move only matching file names.
- `EXCLUDE: patterns` — leave matching names behind; `none` disables defaults.
- `DRY_RUN: yes` — plan and list without changing anything.
- `CONFIRM: yes` — allow more than 200 changes or protected paths.

## Failure boundaries

MOVE refuses without changing anything when:

- the source is missing, is a symlink, or contains symlinks
- a path escapes its root, or the source and destination overlap
- a differing destination file exists and OVERWRITE is no
- a source or existing destination cannot be snapshotted
- the change count or a protected path needs CONFIRM: yes

## Related operations

Use COPY to keep the source.

Use DIFF and REVERT to inspect or recover every recorded file.