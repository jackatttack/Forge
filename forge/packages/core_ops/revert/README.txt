# REVERT

## Summary

REVERT restores project files to their pre-run state using the recovery
snapshots stored with one completed Forge run.

It is a whole-run recovery operation. It cannot restore only one chosen file
from a run that touched several files.

## Choose the run

Find the latest stored stamp:

    FORGE runs latest

Inspect it before recovery:

    DIFF 20260831_120000

Then revert the explicit stamp:

    REVERT 20260831_120000

REVERT requires the actual run stamp. `latest` is not resolved as shorthand;
use `FORGE runs latest` to discover the stamp first.

## Recovery rules

For every path recorded as touched by the selected run:

- if the path existed before the run, its previous text snapshot is restored
- if it did not exist before the run, the current file or directory is deleted
- all recorded paths are processed; there is no per-file selector

This reverses the selected run’s recorded filesystem effects.

## Drift and partial recovery

REVERT does not compare the current file with the run’s after-snapshot before
writing. If the file changed again after the selected run, REVERT still
overwrites it with the older before-snapshot.

Use `DIFF <stamp>` first. DIFF reports whether the current disk has drifted so
newer work can be preserved before recovery.

Recovery is not transactional across all files. REVERT continues after an
individual failure and then reports how many files were restored, deleted, or
failed. A failed REVERT may therefore have applied part of the recovery.

Although the REVERT command may appear in stored run history, the restoration
performed by `revert_run` does not create new before-snapshots for those
writes. Do not rely on undoing a REVERT with another REVERT.

## Directives

REVERT has no user-written directives. The run stamp is written on the
operation line. `ARGS` is internal parser plumbing for that positional stamp.

## BRANCH versus REVERT

Use REVERT when one recorded Forge run should be reversed.

Use BRANCH before a risky sequence spanning several runs, or when you want an
explicit checkpoint of selected files and a standalone recovery script.