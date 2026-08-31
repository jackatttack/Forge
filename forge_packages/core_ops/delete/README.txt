# DELETE

## Summary

DELETE is the reboot public deletion op.

It deletes whole files, explicit file line ranges, or exact old text blocks while recording recovery metadata for DIFF and REVERT.

## Mental model

DELETE means: remove something that already exists.

It is the destructive sibling of REPLACE. REPLACE changes existing content; DELETE removes existing content.

## Use when

- You want to remove a file.
- You want to remove a known line range.
- You want to remove an exact text block.
- You want deletion to be tracked for DIFF and REVERT.

## Do not use when

- You want to change text rather than remove it. Use REPLACE.
- You want to add text. Use INSERT.
- You have not inspected the target. Use READ first.
- You want AST deletion. Not supported yet.

## Syntax

    DELETE scratch/example.txt

    DELETE docs/example.txt
    LINES: 12-15

    DELETE docs/example.txt
    BEGIN_OLD
    exact text to remove
    END_OLD

Delete every exact match only with explicit confirmation:

    DELETE docs/example.txt
    ALL: yes
    CONFIRM: yes
    BEGIN_OLD
    repeated exact text
    END_OLD

## Directives

- LINES: start-end — delete an explicit inclusive file line range.
- OCCURRENCE: N — in exact block mode, delete the Nth matching OLD block.
- ALL: yes — delete every exact OLD match; requires CONFIRM: yes.
- CONFIRM: yes — required for ALL: yes and may also be required by Forge's protected-core guard.

## Notes for LLMs

- Always READ before range or block deletion unless the user gave exact current text.
- Do not use DELETE for AST targets yet.
- Prefer DELETE + LINES for small inspected slices.
- Prefer DELETE + BEGIN_OLD for exact copied blocks when line numbers are awkward.
- Normal precise DELETE does not require CONFIRM.
- Never use ALL: yes casually; ALL: yes requires CONFIRM: yes.
- Protected Forge core targets may independently require CONFIRM: yes.
