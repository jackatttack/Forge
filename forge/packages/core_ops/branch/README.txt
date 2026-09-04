# BRANCH

## Summary

BRANCH creates named checkpoints of selected project files before a risky
sequence of changes.

It complements run-level REVERT:

- REVERT restores every file recorded by one completed Forge run.
- BRANCH captures an explicit file and directory selection before work begins.

## Create a checkpoint

List one project-relative file or directory on each body line:

    BRANCH create before_change
    BEGIN_BODY
    projects/example/app.py
    projects/example/config/
    END_BODY

A directory is expanded recursively when the branch is created. Hidden
directory entries and `__pycache__` folders are skipped during that traversal.

The body is required for `BRANCH create`. There is no implicit whole-project
checkpoint.

Requested paths must remain inside the resolved project root. An escaping path
fails the operation. A path that does not yet exist is not captured; creating
it later will not make BRANCH delete it during restore.

Creating a branch with an existing name replaces that checkpoint.

## List checkpoints

    BRANCH list

The list is scoped to checkpoints belonging to the current resolved project
root and reports each name and captured-file count.

Forge retains up to 100 checkpoints for the current project. Creating another
checkpoint may prune the oldest entries beyond that limit.

## Restore a checkpoint

    BRANCH restore before_change

Restore copies every captured file back to its recorded project-relative
location.

Restore deliberately has narrow semantics:

- captured files overwrite their current contents
- files created after the checkpoint are left alone
- extra files later added inside a captured directory are left alone
- paths that were missing when the checkpoint was created remain untouched
- there is no drift check before overwrite
- restore operates on the entire checkpoint, not one selected file

BRANCH is therefore a selected-file snapshot, not a complete filesystem
rollback.

## Delete a checkpoint

    BRANCH delete before_change

Delete removes the stored checkpoint and its recovery artifacts. It does not
delete project files.

## Standalone recovery

Each successful create reports a `restore_branch.py` path. The script sits
beside the checkpoint manifest under:

    <storage_root>/branches/<name>/

If Forge itself is unavailable, open that returned script directly in
Pythonista and run it. It reads the recorded project root from `manifest.json`
and restores the same captured files without importing Forge.

The standalone script has the same restore limits: it overwrites captured
files but does not remove later-created files.

## Directives

BRANCH has no user-written directives. The subcommand and checkpoint name are
written on the operation line. `ARGS` is internal parser plumbing for that
same-line text.

## Safety notes

Use BRANCH before a multi-run or experimental change whose recovery should not
depend on one run snapshot.

Use `DIFF <stamp>` and REVERT when the change already happened in one recorded
Forge run.

A restore can overwrite newer work without warning. Inspect the checkpoint
name and affected area before restoring.