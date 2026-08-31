# READ

READ is the reboot public inspection verb.

Use it before editing. It answers:

    what is here?

READ is deliberately broad. It can inspect:

- normal files
- line ranges
- Python AST targets
- anchored slices
- Python target lists
- directories, with a compact structural listing

## Decision guide

Read a whole file or default first slice:

    READ app.py

Read a numbered slice:

    READ app.py
    LINES: 1-120

Read a Python function, method, class, or assignment target:

    READ app.py::main

Discover Python targets:

    READ app.py
    TARGETS: yes

Read around an anchor inside a file:

    READ app.py
    ANCHOR: def main
    CONTEXT: 8

Use fuzzy anchor matching when whitespace drift is expected:

    READ app.py
    ANCHOR: if ready:
    MATCH: fuzzy
    CONTEXT: 6

Read a directory as an orientation tree:

    READ docs

Read a deeper directory tree:

    READ docs
    DEPTH: 3
    FILES: yes

## Mental model

READ is the safe first move.

Use READ before:

- INSERT
- REPLACE
- DELETE
- RUN on unfamiliar scripts

READ should usually replace older inspect-only habits unless a specialist op is clearly better.

## Directives

- LINES: start-end — read an inclusive line range.
- ANCHOR: text — read around the first matching line.
- CONTEXT: N — number of lines either side of ANCHOR. Default is 10.
- MATCH: exact or fuzzy — controls ANCHOR matching.
- TARGETS: yes — list Python AST targets in a file.
- DOCS: yes/no — include doc hints in target/directory modes where supported.
- DEPTH: N — directory depth when reading a directory.
- FILES: yes/no — show files in directory mode.
- README: yes/no — include README summaries in directory mode.
- FILTER: text or suffix — pass through to directory mode.
- ALL: yes — include otherwise skipped noisy/system folders in directory mode.

## Modes

READ result data reports a mode:

- file
- ast
- targets
- directory

The Surface uses this mode to render a dashboard, source view, target list, or directory view.

## Recommended workflows

Before replacing a function:

    READ app.py
    TARGETS: yes

    READ app.py::main

    REPLACE app.py::main
    BEGIN_BODY
    def main():
        return True
    END_BODY

Before a line-range edit:

    READ docs/example.txt
    LINES: 1-80

    REPLACE docs/example.txt
    LINES: 22-25
    BEGIN_BODY
    replacement text
    END_BODY

Before an anchored insert:

    READ app.py::main

    INSERT app.py::main
    ANCHOR: if ready:
    POSITION: after
    INDENT: child
    BEGIN_BODY
    run()
    END_BODY

## Related ops

- MAP — structural directory and project orientation.
- SEARCH — find files or text before reading.
- INSERT — add new content.
- REPLACE — change existing content.
- RUN — execute inspected scripts.