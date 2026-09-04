# COPY

## Summary

COPY duplicates one project-relative text file at another project-relative
path.

The source is read but never changed. Only the destination is recorded as a
mutation.

## Copy a file

    COPY scratch/source.py
    TO: scratch/copy.py

`TO` is required. Both paths are resolved inside the current project root.

COPY handles one regular text file. It does not copy directories or directory
trees.

## Replace an existing destination

COPY protects an existing destination by default:

    COPY scratch/source.py
    TO: scratch/existing.py
    OVERWRITE: yes

Without `OVERWRITE: yes`, an existing destination makes the operation fail
without writing.

`OVERWRITE` controls the destination replacement directly. COPY has no
`CONFIRM` directive.

## Recovery

A successful COPY records the destination's real previous state.

If the destination already existed, REVERT can restore its former contents. If
COPY created it, REVERT can remove it as part of reverting the recorded run.

The source is not recorded as touched because COPY does not modify it.

## Manual move workflow

Forge has no public MOVE operation. To move a file safely:

    COPY old/path.txt
    TO: new/path.txt

Inspect or test the new path, then remove the original deliberately:

    DELETE old/path.txt

A precise whole-file DELETE does not require confirmation. Protected-core
rules may still require confirmation when their target matches a protected
path.

## Directives

- `TO: path` — required project-relative destination.
- `OVERWRITE: yes` — deliberately replace an existing destination file.

## Failure boundaries

COPY fails without writing when:

- the source is missing or is not a regular file
- either path escapes the project root
- the destination exists without `OVERWRITE: yes`
- the destination exists but is not a regular file
- reading or writing raises an I/O error

COPY reads and writes text using Forge's normal UTF-8 file helpers. It is not a
binary-file or metadata-preserving filesystem copy.

## Related operations

Use READ to inspect the source or destination.

Use WRITE or REPLACE when the destination content should differ from the
source.

Use DELETE only after verifying a manual move.

Use DIFF and REVERT to inspect or recover the recorded destination change.