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

A copy that would change more than 200 files needs CONFIRM: yes. Check big
copies with DRY_RUN first.

## Planning before writing

COPY checks paths, overlap, conflicts, filters, protection, the file limit,
and readable source/destination snapshots before changing project files.
A planning problem refuses the whole copy.

Binary files are supported automatically, with no extra directive.
PNG images, audio, archives and other ordinary files are copied byte-for-byte,
as are text files including their original line endings.

Binary and large files use chunked I/O and file-backed snapshots. Small
UTF-8 text remains available for line diffs. DIFF reports byte counts and
SHA-256 checksums for binary/large files instead of printing their contents.

Each destination is written to a verified temporary file beside the target,
then installed atomically. A destination that changed since planning is
refused. Temporary snapshots require disk space; DRY_RUN may create temporary
snapshots but does not change source or destination files.

## Recovery

REVERT restores replaced and removed files and deletes created ones.
Folders COPY created are left behind, empty, as with WRITE.

An I/O error part-way through stops the copy. Completed changes are recorded,
so REVERT can undo the recorded partial copy. A failed staged write leaves
its existing destination intact.

REVERT checks current contents and snapshot checksums before recovery and
refuses newer edits. Existing text run records remain supported. Recovery
is itself recorded and can be reverted.

Run evidence is persisted when the bundle finishes. Transfers are not a
crash-atomic multi-file transaction and do not lock out concurrent writers.

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
- a source or existing destination cannot be snapshotted
- the change count or a protected path needs CONFIRM: yes

## Related operations

Use MOVE when the source should be removed after copying.

Use MAP to inspect a directory before copying it.

Use DIFF and REVERT to inspect or recover every recorded file.