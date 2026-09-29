# INSERT

## Summary

INSERT adds code or text without removing existing content.

The target shape chooses between syntax-aware Python insertion and verbatim
plain-file insertion.

## Decision guide

Add text beside a line you have seen, in any file:

    INSERT docs/notes.md
    ANCHOR: ## Setup
    POSITION: after
    BEGIN_BODY
    new line
    END_BODY

Add a sibling function or class beside an existing Python target:

    INSERT app.py::existing_function
    POSITION: after
    BEGIN_BODY


    def new_helper():
        return True
    END_BODY

Add code inside a function, method, class, or other body-owning target:

    INSERT app.py::main
    POSITION: end
    BEGIN_BODY
    print("done")
    END_BODY

Add code relative to a line inside one resolved AST target:

    INSERT app.py::main
    ANCHOR: if ready:
    POSITION: after
    INDENT: child
    BEGIN_BODY
    run()
    END_BODY

Add text at an inspected line number in a plain file:

    INSERT docs/example.txt
    LINE: 4
    POSITION: after
    BEGIN_BODY
    new line
    END_BODY

Prefer ANCHOR over LINE. An anchor finds its line by content, so it still
lands correctly after earlier edits have shifted line numbers.

## Anchors

ANCHOR matches any line containing the anchor text. In a plain file Forge
searches the whole file; with path::Target it searches only inside that
target, keeping the edit narrow.

Without OCCURRENCE or EXPECT the anchor must match exactly once. A repeated
anchor is refused rather than guessed.

Pick one of several matches with OCCURRENCE alone, the same as REPLACE:

    INSERT notes.txt
    ANCHOR: TODO
    POSITION: after
    OCCURRENCE: 2
    BEGIN_BODY
    inserted after the second TODO line
    END_BODY

Add EXPECT: N when you also want the total number of matches asserted.
The insert is refused if the count differs.

## Whitespace

The two insertion families treat the body differently, because they have
different jobs.

Plain-file insertion writes the body exactly as given. Leading spaces,
relative indentation, and blank lines between body lines all survive.
Blank lines at the very start or end of the body are dropped. Indentation is often
the meaning of the line in YAML, Markdown, or indented configuration, so
Forge does not touch it:

    INSERT .github/workflows/ci.yml
    ANCHOR: steps:
    POSITION: after
    BEGIN_BODY
          - name: Run tests
            run: python -m unittest
    END_BODY

Those six and eight leading spaces reach the file unchanged.

AST insertion re-aligns the body to its destination in the syntax tree.
Write the body at whatever indentation reads naturally and Forge places
it correctly inside the target:

    INSERT app.py::main
    POSITION: end
    BEGIN_BODY
    print("done")
    END_BODY

That lands indented inside main, not at column zero.

INDENT applies only to anchored AST insertion. It has no effect on
plain-file insertion, where the body is already verbatim.

## Target shapes

### Plain-file insertion

    INSERT docs/file.txt
    ANCHOR: text on an existing line
    POSITION: before

or:

    INSERT docs/file.txt
    LINE: 12
    POSITION: after

Plain files need exactly one of ANCHOR or LINE.

### AST sibling insertion

    INSERT file.py::target
    POSITION: before

or:

    INSERT file.py::target
    POSITION: after

This inserts before or after the complete resolved target. It is usually the
safest way to add a top-level helper or class.

### AST body insertion

    INSERT file.py::function_name
    POSITION: start

or:

    INSERT file.py::function_name
    POSITION: end

This inserts inside the resolved function, method, class, or other body-owning
target.

### AST anchored insertion

    INSERT file.py::target
    ANCHOR: if ready:
    POSITION: after
    INDENT: child
    BEGIN_BODY
    inserted_code()
    END_BODY

## Directives

### Placement

- `POSITION: before|after` works with plain files, anchors, and AST siblings.
- `POSITION: start|end` inserts inside an AST body.
- `ANCHOR: text` places the body beside the line containing that text.
- `LINE: N` is a one-based line number in a plain file. Use LINE or ANCHOR,
  not both.

### Anchor matching

- `MATCH: exact|fuzzy` controls anchor matching; default `exact`. Fuzzy
  ignores leading and trailing whitespace.
- `OCCURRENCE: N` selects the Nth match and works on its own.
- `EXPECT: N` asserts the total number of matches.
- `INDENT: auto|same|child` controls AST placement indentation; default
  `auto`.

### Protected targets

`CONFIRM: yes` approves an intentional insertion only when Forge's shared core
guard identifies the target as protected. Inspect the target and create a
BRANCH before confirming a core edit.

### Version pins

`IF_VERSION: <version>` refuses the insert if the file changed since that
version was read.

## Result preview

A successful insert reports the lines where the body landed, with two lines
of numbered context either side. Inserted lines are marked with `>`:

    landed: lines 3-3
      0001: alpha
      0002: beta
    > 0003: new line
      0004: gamma

Check this instead of re-reading the file.

## Refusals and recovery

Rule violations, such as a plain file with neither ANCHOR nor LINE, are
found before the bundle runs. Nothing in the bundle executes and the packet
reports FAILED_PARSE.

Problems that depend on the file are found when the INSERT runs:

- SKIPPED_ANCHOR_MISMATCH: the anchor matched zero times, more than once
  without OCCURRENCE, or a different number of times than EXPECT.
- FAILED_NOT_FOUND: the file, target, or LINE does not exist.
- FAILED_COMPILE: the result would not compile; the file is untouched.

These stop later mutating operations in the bundle. Successful changes record
before-state metadata for DIFF and REVERT.

## Choosing the operation

Use INSERT when adding content.

Use REPLACE when changing content that already exists.

Use WRITE with `CONFIRM: overwrite` when intentionally replacing an entire
existing file.

## Notes for LLMs

- Prefer ANCHOR with text copied from a line you have READ; it survives
  earlier edits in the same bundle.
- Use LINE only with a line number from a fresh READ.
- Plain-file insertion is verbatim; reproduce every required leading space.
- AST insertion re-aligns naturally written code to its destination.
- A repeated anchor needs OCCURRENCE; add EXPECT only to assert the total.
- Confirm placement from the landed lines in the preview.