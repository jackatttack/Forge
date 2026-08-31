# DIFF

## Summary

DIFF reviews file changes recorded by Forge run snapshots.

It is a recovery and inspection op, not a mutating op.

## Mental model

Forge records touched files when write ops run.

DIFF answers:

    What files changed?
    Were they created or modified?
    How large was the change?
    Has the current disk drifted since the stored snapshot?

`DIFF current` reviews changes already made earlier in the same running bundle.

`DIFF latest` or `DIFF <stamp>` reviews a stored run.

## Default behaviour

DIFF is compact by default.

    DIFF current

Compact mode shows one summary per touched file:

- created / modified / touched
- line count before and after
- changed line ranges
- whether current disk has drifted

This is the normal mode for day-to-day review.

## Full mode

Use full mode only when you need line-by-line detail.

    DIFF current
    MODE: full

    DIFF latest
    MODE: full

    DIFF 20260511_120000
    MODE: full

Full mode can be verbose. Prefer compact mode unless the exact changed lines matter.

## Common workflows

Review changes made earlier in the same bundle:

    DIFF current

Inspect the previous stored run:

    DIFF latest

Inspect a specific run:

    DIFF 20260511_120000

Inspect a specific run in full detail:

    DIFF 20260511_120000
    MODE: full

## Notes for LLMs

- Do not use DIFF automatically after every documentation-only update.
- The run packet is the source of truth.
- Use DIFF when it improves review confidence.
- Prefer compact mode by default.
- Use MODE: full only for risky code edits, suspicious drift, or exact line inspection.
- After changing Forge core behaviour, still run smoke checks and AUDIT.