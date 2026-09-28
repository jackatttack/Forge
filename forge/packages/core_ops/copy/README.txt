# COPY

## Summary

COPY copies one file or a whole directory tree to a new path. Either path
may use a named root such as icloud:, so copies work between roots in both
directions.

The source is read but never changed. Every destination file COPY creates,
replaces or removes is recorded, so Changed files, DIFF and REVERT cover the
whole copy.

## Copy a file

    COPY scratch/source.py
    TO: scratch/copy.py

## Copy a directory

    COPY icloud:projects/old_game/game
    TO: icloud:projects/maths_games/games/multiple_merge

TO names the destination itself, never a folder to copy into. After this
copy, games/multiple_merge mirrors game/. A trailing slash changes nothing.

## Existing destination files

OVERWRITE decides what happens to files already at the destination:

- no (default): refuse the whole copy if any existing file differs.
  Identical files are left alone and reported as unchanged.
- yes: replace differing files; keep destination files the source lacks.
- replace: make the destination match the source, removing destination
  files the source lacks. Removed files are recorded too.

Filters apply to replace as well: a destination file that GLOB or EXCLUDE
would skip is never removed.

## Filters

    COPY projects/tilekit/tilekit
    TO: icloud:projects/maths_games/tilekit
    OVERWRITE: replace
    EXCLUDE: scratch

EXCLUDE skips names at any depth and adds to the defaults: __pycache__,
*.pyc, .DS_Store and script_snapshots. EXCLUDE: none switches the defaults
off. GLOB keeps only files whose names match, for example GLOB: *.py, *.md.
Filters apply to directory copies only.

## Preview first

    COPY projects/big_folder
    TO: icloud:projects/big_folder
    DRY_RUN: yes

A dry run plans and lists the copy without writing anything.

## Limits and confirmation

A copy that would change more than 200 files needs CONFIRM: yes, as does a
copy that changes protected core paths. Check big copies with DRY_RUN first.

## Planning before writing

COPY checks everything before it writes: paths, overlap, conflicts,
filters, protection, the file limit, and that every file is UTF-8 text. Any
problem refuses the whole copy and nothing is written.

Binary files are not supported yet, because run recovery stores text. A
file that is not UTF-8 refuses the copy and is named; skip it with EXCLUDE.

## Recovery

REVERT restores replaced and removed files and deletes created ones.
Folders COPY created are left behind, empty, as with WRITE.

An I/O error part-way through stops the copy. Every file written before it
is recorded, so REVERT undoes the partial copy.

## Moving

Use MOVE to copy, verify and then remove the source in one recorded step.

## Directives

- `TO: path` — required destination path itself.
- `OVERWRITE: no|yes|replace` — policy for existing destination files.
- `GLOB: patterns` — keep only matching file names in a directory copy.
- `EXCLUDE: patterns` — skip matching names; `none` disables defaults.
- `DRY_RUN: yes` — plan and list without writing.
- `CONFIRM: yes` — allow more than 200 changes or protected paths.

## Failure boundaries

COPY refuses without writing when:

- the source is missing, is a symlink, or contains symlinks
- a path escapes its root, or the source and destination overlap
- a differing destination file exists and OVERWRITE is no
- a file is not UTF-8 text
- the change count or a protected path needs CONFIRM: yes

## Related operations

Use MOVE when the source should be removed after copying.

Use MAP to inspect a directory before copying it.

Use DIFF and REVERT to inspect or recover every recorded file.