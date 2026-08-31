INSERT is the reboot unified insertion op.

Purpose
INSERT adds code or text without removing existing content.

It consolidates the old split insertion family into one predictable surface:

- AST sibling insertion
- AST body insertion
- AST anchor-based insertion
- plain text file line insertion

The goal is to avoid remembering separate ops such as INSERT_BEFORE, INSERT_AFTER, INSERT_INTO, APPEND_INTO, PREPEND_INTO, and INSERT_FILE_LINE.

Core rule
Use one op. Make the destination explicit with the target shape and directives.

Decision guide

Use this pattern when adding a new helper function, class, or sibling code block near existing Python code:

    INSERT app.py::existing_function
    POSITION: after
    BEGIN_BODY


    def new_helper():
        return True
    END_BODY

Use this pattern when adding code inside an existing function or method:

    INSERT app.py::main
    POSITION: end
    BEGIN_BODY
    print("done")
    END_BODY

Use this pattern when adding code under a specific line such as an if, loop, or try block:

    INSERT app.py::main
    ANCHOR: if ready:
    POSITION: after
    INDENT: child
    BEGIN_BODY
    run()
    END_BODY

Use this pattern for plain text files or deliberately inspected flat-file edits:

    INSERT docs/example.txt
    LINE: 4
    POSITION: after
    BEGIN_BODY
    new line
    END_BODY

Target shapes

1. AST sibling insertion

    INSERT file.py::target
    POSITION: before

or:

    INSERT file.py::target
    POSITION: after

This inserts before or after the resolved AST target. It is usually the safest way to add a new top-level helper function or class.

2. AST body insertion

    INSERT file.py::function_name
    POSITION: start

or:

    INSERT file.py::function_name
    POSITION: end

This inserts inside the resolved function, method, class, or body-owning target.

3. AST anchored insertion

    INSERT file.py::target
    ANCHOR: some existing line
    POSITION: before
    INDENT: same
    BEGIN_BODY
    inserted_code()
    END_BODY

or:

    INSERT file.py::target
    ANCHOR: if ready:
    POSITION: after
    INDENT: child
    BEGIN_BODY
    inserted_code()
    END_BODY

ANCHOR searches only inside the resolved AST target. This keeps the edit narrow.

4. Plain file line insertion

    INSERT docs/file.txt
    LINE: 12
    POSITION: after
    BEGIN_BODY
    inserted text
    END_BODY

Plain file insertion requires LINE because there is no AST target to anchor against.

Directives

POSITION:
- before
- after
- start
- end

For AST targets:
- before inserts before the resolved AST target
- after inserts after the resolved AST target
- start inserts near the beginning of the resolved AST target body
- end inserts near the end of the resolved AST target body

For plain files:
- only before and after are valid
- LINE: N is required

ANCHOR:
- optional for AST targets
- searches inside the resolved AST target only
- requires POSITION before or after
- failure must not write
- failure produces SKIPPED_ANCHOR_MISMATCH

INDENT:
- auto
- same
- child

Use INDENT: auto by default.
Use INDENT: child when inserting under a block header such as if ready:.
Use INDENT: same when inserting beside the anchor line.

MATCH:
- exact
- fuzzy

Use exact unless whitespace drift is expected.

OCCURRENCE:
- selects which anchor match to use when repeated anchors are deliberate
- default is 1

EXPECT:
- requires an exact number of anchor matches
- default is 1
- this favours safety over guessing

Result data

INSERT result previews now report:

- mode
- position
- target span where available
- insert line where available
- inserted line count
- anchor / indent / match / occurrence / expect where used

Useful visual modes include:

- ast-before
- ast-after
- body-start
- body-end
- anchor-auto
- anchor-same
- anchor-child
- line-before
- line-after

Safety expectations

INSERT must:

- reject missing body
- reject missing target
- reject bad POSITION
- reject bad INDENT
- reject bad MATCH
- reject plain file insert without LINE
- reject plain file POSITION: start/end
- reject anchor plus POSITION: start/end
- not write when validation fails
- not write when anchor resolution fails
- record touched files for DIFF and REVERT
- preserve recovery through REVERT

Preferred usage

Use INSERT when adding code or text.

Use REPLACE when changing something that already exists.

Use REPLACE with LINES when changing an explicit flat-file line range after READ.

Use WRITE with CONFIRM: overwrite when replacing a whole existing file.

Avoid adding new split insertion ops unless a genuinely new insertion model appears.