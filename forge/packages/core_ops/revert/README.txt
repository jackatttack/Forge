# REVERT

## Summary

REVERT restores project files to their pre-run state using recovery data
stored with one completed Forge run.

It checks every target and snapshot before changing project files. Current
contents and existence must match the selected run's recorded final state.

## Choose the run

Find a stored stamp and inspect its changes:

    FORGE runs latest

    DIFF 20260831_120000

Recover using the explicit stamp:

    REVERT 20260831_120000

REVERT requires the actual run stamp. `latest` is not resolved as shorthand;
use `FORGE runs latest` to discover the stamp first.

## Recovery rules

- All recorded paths are checked before restoration begins.
- Files that existed before the selected run are restored from verified text.
- Files created by the selected run are removed only if they still match.
- Empty files and absent files are distinct states.
- Directories, symlinks, escaping paths and damaged snapshots are refused.
- REVERT never recursively deletes a directory.
- Multiple edits of one path retain its original and final recorded states.

Current file has drifted: recovery is refused before mutation. Inspect the
selected run and reconcile newer work explicitly; there is no force option.

A repeated REVERT will normally refuse because the first recovery changed
the recorded final state. Inspect its result instead of blindly retrying.

## Older records

Recovery records without explicit existence metadata are refused. Older
records cannot reliably distinguish deletion from writing an empty file.
Their snapshots remain available for inspection and deliberate manual recovery.

Extensions that supply their own touched-file dictionaries must include
existed_before and existed_after as booleans, plus before and after text.
The shared touched_file helper supplies this metadata. Whole-file deletion
must explicitly pass existed_after=False.

## Partial recovery and recovery of a REVERT

Recovery is not transactional across all files.

After preflight, each target is checked again immediately before installation.
Restored text is staged beside its destination and installed with os.replace.
Deletion removes only a checked ordinary file.

If an I/O failure or intervening change is detected, recovery stops. Earlier
completed changes are recorded and included in the returned run. After that
run is stored successfully, its stamp can itself be reverted.

This does not provide process isolation, a lock against concurrent writers,
or crash-safe journaling. Another writer can still race the final check.
A process termination or failure to persist the run can prevent recovery of
its completed changes.

Recovery restores recorded UTF-8 text and existence, not historical ownership,
timestamps, permissions or original byte encodings. Existing destination
permission bits are preserved when replacing a file; recreated files use
the staging file's permissions.

## Directives

REVERT has no user-written directives. The run stamp is written on the
operation line. ARGS is internal parser plumbing for that positional stamp.

## BRANCH versus REVERT

Use REVERT when one recorded Forge run should be reversed.

Use BRANCH before a risky sequence spanning several runs, or when you want an
explicit checkpoint of selected files and a standalone recovery script.
BRANCH restore has its own overwrite semantics; these REVERT checks do not
change BRANCH behaviour.