# WRITE

## Summary

WRITE creates a complete file or deliberately replaces an existing file in
full.

Create a new file:

    WRITE scratch/example.txt
    BEGIN_BODY
    hello
    END_BODY

Overwrite a different existing file:

    WRITE scratch/example.txt
    CONFIRM: overwrite
    BEGIN_BODY
    replacement
    END_BODY

The overwrite value is the literal word `overwrite`. `CONFIRM: yes` is not a
substitute for full-file replacement.

## Directives

- `CONFIRM: overwrite` permits replacement of a different existing file.
- `ALLOW_BROKEN: yes` bypasses Python compilation for a deliberately invalid
  fixture.

For example, a parser test may intentionally need invalid Python:

    WRITE tests/fixtures/broken_syntax.py
    ALLOW_BROKEN: yes
    BEGIN_BODY
    def deliberately_broken(
    END_BODY

Do not use `ALLOW_BROKEN` merely to get past an unexpected compile failure.
Fix ordinary Python source instead.

## Rules

- a missing target file is created
- identical existing content is left unchanged without confirmation
- different existing content requires `CONFIRM: overwrite`
- directories cannot be overwritten
- paths must remain inside the project root
- Python content compiles before disk mutation unless explicitly bypassed
- successful changes record recovery metadata for DIFF and REVERT

## Choosing the operation

Use WRITE when supplying the complete intended file.

Use REPLACE for a surgical change inside an existing file.

Use INSERT when adding content without replacing the whole file.