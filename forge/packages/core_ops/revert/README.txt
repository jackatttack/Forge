REVERT
======

REVERT restores project files using recovery snapshots stored with a previous
Forge run.

REVERT is Forge's public run-level recovery operation.

Example:

    FORGE runs latest

    REVERT 20260831_120000

If a touched file did not exist before the selected run, REVERT deletes it.

If it existed before the selected run, REVERT restores the previous content.

Use DIFF <stamp> first when you want to inspect the change before recovering.