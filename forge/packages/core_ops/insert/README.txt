# INSERT

## Summary

INSERT adds code or text without removing existing content.

The target shape chooses between syntax-aware Python insertion and verbatim
plain-file insertion.

## Decision guide

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

Add text at an inspected line in a plain file:

    INSERT docs/example.txt
    LINE: 4
    POSITION: after
    BEGIN_BODY
    new line
    END_BODY

## Whitespace

The two insertion families treat the body differently, because they have
different jobs.

Plain-file insertion writes the body exactly as given. Leading spaces,
relative indentation, and blank lines all survive. Indentation is often
the meaning of the line in YAML, Markdown, or indented configuration, so
Forge does not touch it:

    INSERT .github/workflows/ci.yml
    LINE: 12
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

ANCHOR searches only inside the resolved AST target, keeping the edit narrow.

### Plain-file line insertion

    INSERT docs/file.txt
    LINE: 12
    POSITION: after
    BEGIN_BODY
    inserted text
    END_BODY

Plain-file insertion requires `LINE` because it does not perform anchor
resolution.

## Directives

### Placement

- `POSITION: before|after` works with AST siblings, AST anchors, and plain
  file lines.
- `POSITION: start|end` inserts inside an AST body.
- `LINE: N` is a one-based line number and is required for plain files.

### Anchored AST insertion

- `ANCHOR: text` searches inside the resolved AST target.
- `MATCH: exact|fuzzy` controls anchor matching; default `exact`.
- `INDENT: auto|same|child` controls placement indentation; default `auto`.
- `EXPECT: N` requires exactly N anchor matches; default `1`.
- `OCCURRENCE: N` selects the Nth match; default `1`.

Repeated anchors require both count and selection:

    INSERT app.py::main
    ANCHOR: print("same")
    POSITION: after
    INDENT: same
    EXPECT: 2
    OCCURRENCE: 2
    BEGIN_BODY
    run_after_second_match()
    END_BODY

`OCCURRENCE: 2` alone fails when two anchors exist because the default
`EXPECT: 1` still requires exactly one match.

### Protected targets

`CONFIRM: yes` approves an intentional insertion only when Forge’s shared core
guard identifies the target as protected. Inspect the target and create a
BRANCH before confirming a core edit.

## Refusals and recovery

INSERT refuses invalid placement combinations, missing bodies, missing
targets, unresolved or unexpectedly repeated anchors, and edits that would
leave a Python file unable to compile.

Validation and anchor failures write nothing. Successful changes record
before-state metadata for DIFF and REVERT.

## Choosing the operation

Use INSERT when adding content.

Use REPLACE when changing content that already exists.

Use WRITE with `CONFIRM: overwrite` when intentionally replacing an entire
existing file.

## Notes for LLMs

- READ the exact current target or line range before insertion.
- Plain-file insertion is verbatim; reproduce every required leading space.
- AST insertion re-aligns naturally written code to its destination.
- For YAML, Markdown, and other whitespace-sensitive files, inspect adjacent
  lines before constructing the body.
- INDENT has no effect on plain-file insertion.
- Set EXPECT and OCCURRENCE together when repeated anchors are deliberate.