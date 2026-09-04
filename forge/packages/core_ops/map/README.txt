# MAP

## Summary

MAP shows the structure of a target without dumping its full contents.

Use it when you need orientation before reading, searching, editing, or deciding where to inspect next.

MAP is READ's cousin:

- READ shows source/content.
- SEARCH locates symbols or text.
- MAP explains structure and suggests useful next actions.

## Mental model

MAP answers:

    What is this thing?
    How is it shaped?
    What are its important files, imports, targets, and entrypoints?
    What should I inspect next?

It is designed to provide condensed context for code.

## Default behaviour

    MAP path

MAP auto-detects the target:

- directory -> source-focused directory structure map
- Python file -> Python module map
- other file -> basic file map

`MODE: auto` is the default and should usually be tried first.

## Directory maps

Directory maps show:

- file and directory counts
- Python file count
- README/doc hints
- evidence-ranked likely Python entrypoints
- child folders/files
- suggested next MAP/READ commands

Directory maps are source-focused by default. They skip common noisy folders such as:

- __pycache__
- .git
- site-packages / site-packages-2 / site-packages-3
- artifacts / snapshots
- patch_runs / script_snapshots
- build / dist / node_modules / .venv

Examples:

    MAP forge

    MAP forge/forge/packages
    DEPTH: 2

    MAP forge/forge/packages/core_ops/map

Good use cases:

- starting work in an unfamiliar project
- understanding package layout
- finding likely entry files
- choosing a smaller target before READ

## Python file maps

Python maps show:

- line count
- module docstring summary
- import structure with local path resolution
- classes/functions/methods/assignments
- READ-ready target names
- suggested MAP commands for local dependencies

Example:

    MAP forge/forge/core/runner.py

Good use cases:

- understanding one file without dumping all source
- seeing what a module imports and where they resolve to
- finding READ targets quickly
- choosing between reading SPEC, HELP, validate, execute, or helper functions

## Smart defaults for large files

Large Python files are summarised automatically.

A file is treated as large when it has many lines (>700), many targets (>35), or many imports (>40).

For large files, MAP avoids dumping every method by default. Instead it shows:

- import summary with local dependency count
- external dependency list
- target counts by kind
- target highlights (ranked by likely importance)
- safer suggested READ targets (avoids huge classes)

Use `MODE: targets` when you deliberately want the full target list.

Use `MODE: imports` when you deliberately want the full import list.

## Modes

    MAP path
    MODE: auto

    MAP file.py
    MODE: targets

    MAP file.py
    MODE: imports

    MAP file.py
    MODE: relationships

Mode behaviour:

- auto: choose a sensible map for the target. Shows both imports and targets.
- targets: target-focused view. Suppresses import sections and dependency maps.
- imports: import-focused view. Suppresses target sections and suggested reads.
- relationships: Python-file relationship view. Indexes the containing project scope and shows reverse imports plus statically resolved external callers.

Relationship mode is intentionally opt-in because it scans a wider project scope than normal file mapping.

Worked relationship example:

    MAP forge/forge/core/runner.py
    MODE: relationships

This scans the containing project scope and reports files that import
`runner.py` plus statically resolved callers of its symbols. It is opt-in
because the wider index is more expensive than an ordinary file map.
Each mode shows only its relevant sections to keep output focused.
Hide documentation snippets when only structure matters:

    MAP forge/forge/packages/core_ops/map
    DOCS: no

## Directives

- MODE: auto, targets, imports, or relationships.
- DEPTH: N — directory depth. Default: 1. Maximum: 5.
- LIMIT: N — cap listed rows. Default: 80.
- DOCS: yes/no — include README/docstring snippets. Default: yes.

## Common workflows

Start a cold project inspection:

    MAP forge

Inspect a package:

    MAP forge/forge/packages/core_ops/search

Inspect a Python file:

    MAP forge/forge/core/runner.py

Inspect just imports and dependencies:

    MAP forge/forge/core/runner.py
    MODE: imports

Inspect just READ targets:

    MAP forge/forge/packages/core_ops/map/op.py
    MODE: targets

Increase directory depth carefully:

    MAP forge/forge/packages
    DEPTH: 2
    LIMIT: 120

## When to use MAP

Use MAP when:

- the target is unfamiliar
- broad READ would dump too much content
- you need a compact structural overview
- you want READ-ready AST targets
- you want to see local imports/dependencies
- you are deciding where to inspect next

Use READ when:

- you already know the exact file or target
- you need source content
- you need exact text for a patch

## Current limits

MAP is structural, not a runtime dependency tracer.

It can show:

- directory structure
- README/doc hints
- evidence-ranked likely Python entrypoints
- Python imports with local path resolution
- AST targets
- large-file summaries
- reverse imports in relationship mode
- statically resolved external callers in relationship mode
- self-filtering (won't suggest mapping a file from itself)

### Relationship resolution

Relationship mode currently understands:

- same-file function calls
- same-class `self.method(...)` and `cls.method(...)` calls
- `from module import symbol` including aliases
- `import module` including aliases followed by `module.symbol(...)`

It does not yet fully resolve:

- arbitrary dynamic dispatch
- runtime-generated or dynamic imports
- inheritance and polymorphic method dispatch
- import cycles
- complete transitive call graphs
- repeated class structure detection

## Notes for LLMs

- Use MAP before broad READ on unfamiliar projects.
- Use MAP on directories to choose where to inspect next.
- Use MAP on Python files to get imports and READ-ready AST targets.
- Prefer MAP when the question is structural.
- Prefer MAP over broad READ when token pressure matters.
- Do not suggest Class.* for very large classes unless explicitly requested.
- Use MODE: imports for dependency orientation (suppresses targets).
- Use MODE: targets for complete target listings (suppresses imports).
- Use MODE: relationships when reverse imports or external callers matter.
- Use SEARCH when looking for a specific symbol or phrase.
- MAP is read-only and never modifies files.