# DELETE

## Summary

DELETE removes one file, an inclusive file line range, or an exact text block.

It is file-only. DELETE refuses directory paths and does not recursively remove
directories.

## Syntax

Delete one exactly named file:

    DELETE scratch/example.txt

A whole-file deletion does not require confirmation merely because it removes
the file. The exact project-relative path is the scope, and the successful run
records recovery data.

Delete an inspected inclusive line range:

    DELETE docs/example.txt
    LINES: 12-15

Delete one exact block:

    DELETE docs/example.txt
    BEGIN_OLD
    exact text to remove
    END_OLD

OLD blocks are literal and exact-only. There is no fuzzy matching mode.

If the block occurs more than once, select one match:

    DELETE docs/example.txt
    OCCURRENCE: 2
    BEGIN_OLD
    repeated exact text
    END_OLD

Delete every exact match only with explicit confirmation:

    DELETE docs/example.txt
    ALL: yes
    CONFIRM: yes
    BEGIN_OLD
    repeated exact text
    END_OLD

## Directives

- `LINES: start-end` deletes an inclusive file line range.
- `OCCURRENCE: N` deletes the Nth exact OLD-block match.
- `ALL: yes` deletes every exact OLD match and requires `CONFIRM: yes`.
- `CONFIRM: yes` also approves an intentional edit when the shared core guard
  identifies the target as protected.

## Directories and AST targets

DELETE refuses directory paths with “target exists but is not a file”. Name
individual files explicitly instead.

AST deletion such as `DELETE app.py::main` is not supported. Use READ to
inspect the containing lines and then delete an explicit range or exact block.

## Failures

Exact-block failures follow the same rules as REPLACE:

- zero matches means the copied text differs from the current file
- repeated matches require `OCCURRENCE` or confirmed `ALL`
- whitespace and blank lines are significant

DELETE also refuses a change that would leave a Python file unable to compile.

## Recovery

Every successful DELETE records touched-file metadata. The returned run packet
contains the run stamp.

Inspect the stored change:

    DIFF 20260904_120000

Restore the deleted file or text:

    REVERT 20260904_120000

REVERT operates on the entire recorded run, so check whether that run touched
other files before recovering it.

## Notes for LLMs

- READ before range or block deletion unless exact current text was supplied.
- A precise whole-file path does not require confirmation.
- Never use `ALL: yes` casually.
- Use REPLACE when existing content should change rather than disappear.