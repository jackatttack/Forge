# REPLACE

## Summary

REPLACE is the reboot unified surgical replacement op.

It replaces an AST target, an explicit file line range, or an exact old/new text block while recording recovery metadata for DIFF and REVERT.

## Mental model

REPLACE means: change something that already exists.

Use INSERT when adding new content. Use REPLACE when existing content should be changed.

Current modes:

- AST mode: file.py::target
- line range mode: LINES: start-end
- exact block mode: BEGIN_OLD / BEGIN_NEW

Full-file overwrite is deliberately not part of REPLACE. Use WRITE with CONFIRM: overwrite when you explicitly mean to replace an entire file.

## Use when

- You want to surgically change existing code or text.
- You have inspected the target with READ first.
- You want the edit recorded for DIFF and REVERT.
- You want one public verb for AST replacement, line ranges, and exact block replacement.
- You want syntax that is readable to both the user and the LLM.

## Do not use when

- You want to add text without removing existing text. Use INSERT.
- You want to overwrite a whole file. Use WRITE with CONFIRM: overwrite.
- You want to create a new file. Use WRITE.
- You are unsure what currently exists. READ first.
- You are targeting repeated exact text without choosing OCCURRENCE or ALL.

## Decision guide

Use AST replacement for whole Python targets:

    READ app.py
    TARGETS: yes

    READ app.py::main

    REPLACE app.py::main
    BEGIN_BODY
    def main():
        return True
    END_BODY

Use line ranges for small inspected text slices:

    READ docs/example.txt
    LINES: 1-40

    REPLACE docs/example.txt
    LINES: 12-15
    BEGIN_BODY
    replacement text
    END_BODY

Use exact OLD/NEW blocks when line numbers are awkward but the current text is known exactly:

    READ docs/example.txt

    REPLACE docs/example.txt
    BEGIN_OLD
    old exact text
    END_OLD
    BEGIN_NEW
    new exact text
    END_NEW

## AST target replacement

Use this when replacing a whole function, method, class, or assignment target.

Common target shapes:

    REPLACE app.py::main
    REPLACE app.py::SomeClass.method
    REPLACE app.py::SomeClass.*
    REPLACE app.py::@SETTING
    REPLACE app.py::SomeClass.@SETTING

## Explicit line range replacement

Use this when replacing a known file slice after inspecting numbered lines.

    REPLACE docs/example.txt
    LINES: 12-15
    BEGIN_BODY
    replacement text
    END_BODY

Line ranges are inclusive.

## Multiple line-range edits in one file

When doing more than one REPLACE with LINES in the same file, apply later line numbers first.

Good order:

    REPLACE app.py
    LINES: 80-90
    BEGIN_BODY
    later replacement
    END_BODY

    REPLACE app.py
    LINES: 20-25
    BEGIN_BODY
    earlier replacement
    END_BODY

This avoids the first edit shifting the line numbers of later edits.

For many edits in one file, prefer AST targets or exact OLD/NEW blocks when possible.

## Exact old/new block replacement

Use this when line numbers are awkward but the current text can be copied exactly.

For repeated blocks, choose deliberately:

    REPLACE docs/example.txt
    OCCURRENCE: 2
    BEGIN_OLD
    repeated exact text
    END_OLD
    BEGIN_NEW
    replacement text
    END_NEW

To replace every exact match:

    REPLACE docs/example.txt
    ALL: yes
    BEGIN_OLD
    old exact text
    END_OLD
    BEGIN_NEW
    new exact text
    END_NEW

Use ALL: yes carefully.

## Directives

- LINES: start-end — replace an explicit inclusive line range in a plain file.
- OCCURRENCE: N — in exact block mode, replace the Nth matching OLD block.
- ALL: yes — in exact block mode, replace every matching OLD block.
- CONFIRM: yes — used when the core guard requires explicit confirmation.

## Blocks

REPLACE supports these structured blocks:

- BEGIN_BODY / END_BODY — replacement body for AST mode and line range mode.
- BEGIN_OLD / END_OLD — exact current text to find in block mode.
- BEGIN_NEW / END_NEW — exact replacement text to write in block mode.

## Common failures

### Plain file REPLACE requires LINES or BEGIN_OLD/BEGIN_NEW

A plain file path is ambiguous. Forge does not know whether you want a line range, exact block, or whole-file overwrite.

Fix it by using a line range or exact old/new blocks.

### OLD block matched 0 times

The OLD block does not match the current file exactly.

Fix:

- READ the current file.
- Copy the exact old text again.
- Watch whitespace and blank lines.

### OLD block matched multiple times

By default, exact block mode refuses ambiguous repeated matches.

Fix:

- Use OCCURRENCE: N for one deliberate match.
- Use ALL: yes only when replacing every match is intentional.

### REPLACE target was not found

For AST mode, the target string may be wrong or the file may have changed.

Fix:

- Run READ with TARGETS: yes on the file.
- Copy the exact target.
- READ the target before retrying.

## Safety and recovery

Every successful REPLACE records touched-file metadata so DIFF and REVERT can inspect and recover the change.

Branch before risky/core edits.

Full-file replacement is deliberately handled by WRITE with CONFIRM: overwrite because it is more powerful and easier to misuse.

## Related ops

- READ — inspect current files, ranges, anchors, and AST targets.
- READ with TARGETS: yes — find exact AST targets before AST replacement.
- INSERT — add new text/code without replacing existing text.
- WRITE — create files or deliberately overwrite a whole existing file.
- DIFF — review before/after/current state.
- REVERT — recover files from a previous run.
- BRANCH — checkpoint files before risky edits.

## Notes for LLMs

- Inspect first. Use READ before REPLACE unless the user supplied exact current text.
- Prefer AST mode for whole functions, methods, classes, and assignments.
- Prefer REPLACE + LINES for small flat-file edits after READ.
- For multiple LINES edits in the same file, apply later line numbers first.
- Prefer BEGIN_OLD / BEGIN_NEW when line numbers are awkward but exact current text is known.
- Do not use WRITE with CONFIRM: overwrite unless full-file replacement is clearly intended.
- Do not use ALL: yes casually.
- After FAILED_PARSE, follow the packet hint or run FORGE help REPLACE before retrying.
- After a meaningful REPLACE, run the relevant tests or smoke probe.