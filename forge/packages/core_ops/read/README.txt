# READ

## Summary

READ shows the content of a known file or Python target.

It answers:

    What is here?

READ targets files. Use MAP for directory structure and SEARCH when the
location is unknown.

## Decision guide

Read a whole short file or the default first slice:

    READ app.py

Read an inclusive line range:

    READ app.py
    LINES: 1-120

Read a Python function, method, class, or assignment:

    READ app.py::main

List the Python targets that can be addressed directly:

    READ app.py
    TARGETS: yes

Hide docstring summaries from that target list:

    READ app.py
    TARGETS: yes
    DOCS: no

Read around the first exact matching line:

    READ app.py
    ANCHOR: def main
    CONTEXT: 8

Use fuzzy matching when insignificant whitespace may have drifted:

    READ app.py
    ANCHOR: if ready:
    MATCH: fuzzy
    CONTEXT: 6

## Directives

- `LINES: start-end` reads an inclusive line range.
- `ANCHOR: text` reads around the first matching line.
- `CONTEXT: N` controls lines shown either side of `ANCHOR`; default 10.
- `MATCH: exact|fuzzy` controls anchor matching; default exact.
- `TARGETS: yes` lists Python AST targets rather than source.
- `DOCS: yes|no` controls docstring hints in `TARGETS` output; default yes.

## Result modes

READ reports one of three content modes:

- `file` for ordinary file content or a line range
- `ast` for one resolved Python target
- `targets` for a Python target listing

Directories are deliberately not a READ mode. Use:

    MAP docs

## Recommended workflows

Before replacing a known function:

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

## Limits

READ is read-only and never changes files.

It does not map directories, resolve imports, follow references, or trace
runtime behaviour. MAP handles structure and SEARCH locates unknown content.

A broad file read may return a bounded first slice rather than every line.
Request an exact `LINES` range or AST target when the omitted content matters.

`DOCS` only affects Python target listings; it does not change ordinary file or
AST-target reads.

## Notes for LLMs

Use READ when the relevant file or Python target is already known.

Use MAP when the structure is unclear. Use SEARCH when the location is
unclear.

Inspect the exact current range, anchor, or AST target before mutating it.

Do not invent directory controls for READ. `DEPTH`, `FILES`, `README`,
`FILTER`, and `ALL` belong elsewhere and are rejected by READ.