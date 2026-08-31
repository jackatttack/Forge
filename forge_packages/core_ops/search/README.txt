# SEARCH

## Summary

SEARCH is the reboot search op.

Use it for orientation before reading or editing. It supports normal text search
and AST-powered structural search for Python code.

## Mental model

SEARCH finds candidate locations. READ inspects the exact thing.

Text search answers:

    Where does this text appear?

AST search answers:

    Where is this function/import/call/assignment structurally present?

SEARCH is a locator, not a dependency graph engine. Future dependency graph work
belongs in a separate op.

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
    IMPORTS: forge_core.preparse

Find assignments:

    SEARCH forge
    MATCH: ast
    ASSIGNS: SPEC
    CASE: yes

Narrow an AST search to part of the tree:

    SEARCH forge
    MATCH: ast
    CALLS: expand_bundle
    FILTER: forge_core

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

    READ forge/forge_core/runner.py::run_text

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
    IMPORTS: forge_core.preparse

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
    FILTER: forge_packages

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

- QUERY: text — explicit text query. In MATCH: ast, it can act like DEFINES, but prefer explicit AST directives.
- MATCH: exact, fuzzy, regex, or ast.
- EXT: .py,.txt — restrict file extensions.
- LIMIT: N — cap matches. Default: 80.
- CASE: yes — use case-sensitive matching.
- CONTEXT: N — show neighbouring lines for text search.
- FILTER: text — include only matched paths containing this substring.
- EXCLUDE: text,text — exclude matched paths containing any listed substring.
- ACTIVE_ONLY: yes — exclude common archive/reference/staging paths such as archive/, old workspaces, public release staging, and packed/.
- DEFINES: name — AST search for function, method, or class definitions.
- CALLS: name — AST search for function/method calls.
- IMPORTS: module — AST search for import sites.
- ASSIGNS: name — AST search for assignments.

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

Those belong in a future dependency-focused op.

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
