# SEARCH

## Summary

SEARCH locates text or Python structure in project files.

Use it for orientation before reading or editing. It supports normal text search
and AST-powered structural search for Python code.

## Mental model

SEARCH finds candidate locations. READ inspects the exact thing.

Text search answers:

    Where does this text appear?

AST search answers:

    Where is this function/import/call/assignment structurally present?

SEARCH is a locator, not a dependency graph engine. Use
`MAP file.py` with `MODE: relationships` for reverse imports and statically
resolved callers.

## Which mode should I use?

Use normal text search when:
- looking for wording in docs or comments
- finding rough references quickly
- searching non-Python files
- using fuzzy or regex matching

Use AST search when:
- looking for Python definitions
- finding imports
- finding calls to a function
- finding assignments like op SPEC objects
- reducing false positives from plain text grep

## Text syntax

Explicit bundle shape:

    SEARCH forge
    QUERY: package contract

Path-first shortcut:

    SEARCH forge FOR package contract

Query-first shortcut:

    SEARCH package contract IN forge

Prefer the path-first form, `SEARCH path FOR text`, for ordinary searches.
Use `QUERY` when the text is long, awkward, or contains syntax words such as
`IN` or `FOR`.

Single-file search:

    SEARCH forge/smoke.py FOR main

Filtered search:

    SEARCH forge FOR surface
    EXT: .py,.txt
    LIMIT: 40

Fuzzy search:

    SEARCH forge FOR render hints
    MATCH: fuzzy
    CONTEXT: 3

Regex search:

    SEARCH forge
    QUERY: def .*run
    MATCH: regex

## AST syntax

Find a function, method, or class definition:

    SEARCH forge
    MATCH: ast
    DEFINES: run_text

Find calls:

    SEARCH forge
    MATCH: ast
    CALLS: parse_bundle

Find imports:

    SEARCH forge
    MATCH: ast
    IMPORTS: forge.core.preparse

Find assignments:

    SEARCH forge
    MATCH: ast
    ASSIGNS: SPEC
    CASE: yes

Narrow an AST search to part of the tree:

    SEARCH forge
    MATCH: ast
    CALLS: expand_bundle
    FILTER: forge.core

AST mode defaults to Python files only unless EXT is provided.

## AST output

AST search rows include:

- file
- line
- kind
- name
- target
- source line

The target column is the usual next step. Use it with READ when available.

Example workflow:

    SEARCH forge
    MATCH: ast
    CALLS: parse_bundle

Then inspect the returned target:

    READ forge/forge/core/runner.py::run_text

For imports or top-level assignments, the target may be the file rather than a
function target. In that case, READ the file or a nearby line range.

## Common workflows

Find where a runner/function is defined:

    SEARCH forge
    MATCH: ast
    DEFINES: run_text

Find who calls a helper:

    SEARCH forge
    MATCH: ast
    CALLS: expand_bundle

Find coupling to a module:

    SEARCH forge
    MATCH: ast
    IMPORTS: forge.core.preparse

Find all op specs:

    SEARCH forge
    MATCH: ast
    ASSIGNS: SPEC
    CASE: yes

Find likely package/op files only:

    SEARCH forge
    MATCH: ast
    ASSIGNS: SPEC
    CASE: yes
    FILTER: forge.packages

Find text with nearby context:

    SEARCH forge FOR parser rule
    CONTEXT: 3

Search active code while avoiding archive/reference paths:

    SEARCH . FOR render_search_map_html
    ACTIVE_ONLY: yes
    EXT: .py

Search a broad tree but deliberately skip noisy areas:

    SEARCH . FOR def execute
    EXT: .py
    EXCLUDE: archive,workspaces

## Directives

### Matching

- `QUERY: text` supplies an explicit query when shortcut syntax is awkward.
- `MATCH: exact|fuzzy|regex|ast` selects the matching model.
- `CASE: yes` enables case-sensitive matching.
- `CONTEXT: N` adds neighbouring lines to text-search hits.

### Scope

- `EXT: .py,.txt` restricts extensions; see “What a search did not read”.
- `LIMIT: N` caps returned matches; default `80`.
- `FILTER: text` includes only paths containing one substring.
- `EXCLUDE: text,text` excludes paths containing any listed substring.
- `ACTIVE_ONLY: yes` skips common archive, reference, and staging paths.

### Python AST selectors

- `DEFINES: name` finds function, method, or class definitions.
- `CALLS: name` finds function or method calls.
- `IMPORTS: module` finds import sites.
- `ASSIGNS: name` finds assignments.

Use AST selectors with `MATCH: ast`. Prefer them over using `QUERY` as an
implicit definition search.

## What a search did not read

SEARCH never reads every file. Two filters apply before matching:

Extension. Text search defaults to .py, .txt, and .md. AST search
defaults to .py. Configuration and data files such as .yml, .json,
.toml, and .cfg are therefore invisible by default.

    SEARCH . FOR workflow_dispatch
    EXT: all

Directories. Caches, vendored packages, and Forge artifacts are pruned
from the walk, along with dot-directories such as .github.

Because "0 hits" and "never looked" are easy to confuse, results report
their own scope:

    EXT=.md,.py,.txt
    skipped: 147 files by extension (searched .md,.py,.txt — use EXT: all to widen)
    skipped dirs: .github

Those lines appear only when something was actually skipped. A search
that read everything in scope stays quiet.

Treat a zero-hit result with a skip line as inconclusive rather than
negative. Rerun with EXT: all before concluding the text is absent.

## Limits

AST search is syntactic. It does not resolve runtime behaviour.

It finds:
- written imports
- written calls
- written definitions
- written assignments

It does not yet know:
- whether an import is stdlib, third-party, or local
- whether a call is dynamically dispatched
- reverse module dependencies
- import cycles
- full call graphs

Use MAP relationship mode when reverse imports or statically resolved callers
are the real question.

## Notes for LLMs

- Prefer SEARCH path FOR text for simple text searches.
- Use QUERY when the search text is long, awkward, or contains words like IN/FOR.
- Use MATCH: ast when searching Python structure rather than text.
- Use explicit AST directives instead of QUERY in AST mode when possible.
- Use FILTER aggressively on large trees.
- Use EXCLUDE or ACTIVE_ONLY when broad search might include archive/reference copies.
- Use CASE: yes with ASSIGNS: SPEC when looking for op package SPEC objects.
- Text hits include lightweight hit kinds such as function, class, import, assignment, doc, test, comment, or code.
- SEARCH suggests next READ/MAP commands for high-value hits when possible.
- After SEARCH finds candidates, use READ on the specific file or AST target.
- SEARCH is read-only. It should not touch files or create snapshots.
- Treat the dedicated result-scope lines as evidence about what SEARCH actually inspected.
