BRANCH is the reboot named-checkpoint op.

It complements run-level REVERT:
- REVERT reverses one run using touched-file snapshots.
- BRANCH creates a named checkpoint before a risky sequence.

BRANCH create also writes a standalone restore_branch.py script beside the saved manifest so a branch can be restored even if the reboot runner is broken.
