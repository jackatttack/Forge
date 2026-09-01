# Forge

**A portable local execution bridge for human-in-the-loop AI pair programming.**

Forge lets an AI assistant work with code that lives in an environment the
assistant cannot directly control.

The assistant writes a small plain-text **Forge bundle**. You run that bundle
locally. Forge inspects, edits, executes, or recovers project files and returns
a structured **run packet** describing exactly what happened.

The packet is ground truth.

    The assistant proposes.
    The user runs.
    Forge reports.
    The packet confirms.

Forge is pure Python. The portable runtime has no dependency on a particular
IDE, clipboard, UI toolkit, shell, or operating-system integration.


## The idea in 60 seconds

The basic loop is:

    AI assistant
        |
        | Forge bundle
        v
    Portable Forge
        |
        | parse
        | validate
        | execute
        | record
        v
    Canonical run packet
        |
        +----> human
        |
        +----> AI assistant

A host can wrap the two edges:

    get bundle text
        ->
    Forge
        ->
    return rendered result

For example, a terminal can read a file and print the result. Pythonista can
read from the clipboard and put the packet back on the clipboard. Another host
could use a GUI, editor extension, web view, or custom transport.

The center stays portable.

Everything environment-specific lives at the edges.


## What Forge is - and what it is not

Forge is not an autonomous coding agent.

It does not silently control your machine, upload your project, or require the
assistant to have filesystem or shell access.

Forge is a local protocol and runtime.

The AI produces ordinary text. The user chooses whether to run it. Forge
executes that text against an explicit project root and reports the result as
deterministic text.

That makes Forge useful when:

- your AI assistant lives in a separate chat interface;
- your code is on a phone, tablet, embedded system, or unusual Python IDE;
- a full coding-agent integration is unavailable or undesirable;
- you want an explicit human approval step before local execution;
- you want each local action confirmed by an inspectable packet.


## A first Forge loop

An assistant might send:

    MAP .
    DEPTH: 2

    FORGE ops

Save the bundle to a file and run:

    python -m forge bundle.txt

Forge returns something shaped like:

    === FORGE RUN ===
    Run: 20260831_123456
    Mode: dev
    Status: APPLIED

    Ops:
    - APPLIED | MAP | . :: directory mapped
    - APPLIED | FORGE | ? :: 15 public op(s)

    === PREVIEW ===
    ...

    === FORGE SUMMARY ===
    Status: APPLIED
    Ops: 2 applied - 0 skipped - 0 failed
    Changed: 0 files

The assistant reads that packet before deciding what to do next.

Nothing changed merely because the assistant suggested it.


## Quick start

### Pythonista: one-copy install

For a clean Pythonista installation, create any temporary Python script, paste
the following code into it, and run it once:

    import urllib.request

    url = (
        'https://raw.githubusercontent.com/'
        'jackatttack/Forge/v0.1.1/bootstrap/pythonista.py'
    )

    with urllib.request.urlopen(url) as response:
        source = response.read()

    exec(
        compile(
            source,
            'forge_bootstrap.py',
            'exec',
        ),
        {
            '__name__': '__main__',
            '__file__': 'forge_bootstrap.py',
        },
    )

That is the whole bootstrap.

It downloads the Portable Forge installer, installs the runtime into:

    ~/Documents/site-packages-3

and creates:

    ~/Documents/forge_entry.py

On a first installation, the installer opens `forge_entry.py` in Pythonista so
it is ready to use. Existing or updated launchers are left in place without
being auto-opened.

Put a Forge bundle on the clipboard and run `forge_entry.py`.


### 1. Install from a checked-out repository

Portable Forge includes a standard-library-only installer:

    python install.py --source .

The installer places the runtime packages into a Python package directory and
keeps writable Forge state separate from the installed code.


### 2. Read the first-boot guide

Forge ships with a compact operating prompt for an AI assistant:

    python -m forge --first-boot

At the beginning of a cold Forge session, give that text to the assistant.

It establishes the important rules:

- the returned packet is ground truth;
- inspect before editing;
- do not claim local changes without a returned packet;
- read errors and hints before retrying failures;
- orient to the real project and installed Forge language first.


### 3. Run a bundle

From a file:

    python -m forge bundle.txt

From stdin:

    python -m forge < bundle.txt

With an explicit project root:

    python -m forge --project /path/to/project bundle.txt


## The public Forge language

Portable Forge deliberately keeps its normal vocabulary small.

| Area | Operations |
| --- | --- |
| Forge itself | `FORGE` |
| Inspect | `MAP`, `READ`, `SEARCH` |
| Edit | `WRITE`, `REPLACE`, `INSERT`, `DELETE`, `COPY` |
| Execute and recover | `RUN`, `DIFF`, `REVERT`, `BRANCH` |
| Utilities | `URL`, `ALIAS` |

That is 15 public operations.

Ask the installed runtime for the current catalogue:

    FORGE ops

Get help for one operation:

    FORGE help WRITE

Get deeper help:

    FORGE help WRITE full

Inspect all installed operations, including host-specific extensions:

    FORGE ops all

Detailed syntax belongs to each operation's own help. The root README is not
intended to duplicate the full command manual.


## Typical working pattern

A good Forge session is inspect-first.

For example:

    MAP path/to/area

    SEARCH path/to/area FOR "thing_to_find"

    READ path/to/file.py

    REPLACE path/to/file.py::target
    BEGIN_BODY
    ...
    END_BODY

    RUN relevant_test.py

    DIFF current

The exact editing operation depends on the task.

Forge is designed around small grounded changes rather than broad speculative
rewrites.


## Three ways to use Forge

### Standard terminal host

The terminal host is built in:

    python -m forge bundle.txt

Standard Forge prints the canonical packet followed by a small human summary.


### As a Python library

The core loop is deliberately small:

    import forge

    run = forge.run_text(
        bundle,
        project_root="/path/to/project",
    )

    result = forge.render_standard(run)

Forge does not care where `bundle` came from or what you do with `result`.


### Through a host wrapper

A host can provide the two environment-specific edges:

    bundle = get_bundle_text()

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    result = forge.render_standard(run)

    set_result_text(result)

`get_bundle_text()` and `set_result_text()` belong to the host.

The Forge runtime between them does not.

See `examples/minimal_loop.py` for the smallest complete example.


## The packet is the contract

Forge separates execution from claims about execution.

A successful packet can prove that a file was read, changed, executed, or
restored.

A failed packet is useful too. It records the failure rather than requiring the
assistant to guess what happened.

The normal loop is:

    propose
        ->
    run
        ->
    inspect packet
        ->
    decide next action

That distinction is central to Forge.


## Safety model

Forge is intentionally powerful enough to edit and execute project code, so
its boundaries need to remain explicit.


### The complete bundle is parsed first

Forge parses the full submitted bundle before executing operations.

A parser failure does not leave a half-parsed instruction stream.


### Project boundaries are explicit

Project operations resolve against `project_root`.

Portable Forge does not silently discover a hidden working project inside its
core.


### Installed code and writable state are separate

The installed package can be treated as read-only.

Run history, aliases, branches, configuration, and other generated state live
under a writable Forge home.

The standard host uses:

    ~/.forge

unless another location is supplied.


### Mutations are observable

Successful editing operations report touched files and record recovery
information where appropriate.

Use:

    DIFF current

to inspect changes.

Use:

    REVERT <run>

to restore project files from a stored Forge run.


### Destructive scope matters

A precise ordinary `DELETE` expresses deletion intent directly.

Broader destructive scope, such as deleting every matching block with
`ALL: yes`, requires explicit confirmation.

Protected Forge internals may independently require confirmation.


### Installer collisions are blocked

Portable Forge uses the Python package names:

    forge
    forge_core
    forge_packages

The installer checks for namespace collisions before installation.

It refuses to overwrite unrecognised packages merely because they share those
names.

`--force` can replace only an installation carrying Portable Forge's own
installer marker.

This protects existing Forge installations and unrelated Python packages from
accidental replacement.


### Failures are evidence

When a Forge run fails:

1. read `ERRORS`, `HINTS`, and `PREVIEW`;
2. identify the failed operation;
3. follow the Forge hint when present;
4. use `FORGE help <OP>` when syntax is unclear;
5. inspect the relevant state;
6. make the smallest correction;
7. run again and inspect the new packet.

Do not guess Forge syntax after a failure.

See `docs/SAFETY.md` for the fuller model.


## Portable core and host adapters

The central architectural rule is:

**Adapters import Forge. Forge never imports adapters.**

Portable Forge core does not import Pythonista UI modules, clipboard APIs,
editors, terminal wrappers, or other platform adapters.

A host adapter may choose:

- how bundle text is obtained;
- what the project root is;
- where writable Forge state lives;
- what capabilities the environment exposes;
- where output is sent;
- whether richer presentation is available.

A host must not change Forge execution semantics or the meaning of the
canonical packet.

See `docs/HOST_ADAPTERS.md`.


## Environment and configuration

Forge separates persistent wishes from runtime truth.

Configuration describes defaults and preferences.

Environment context describes the resolved runtime:

- project root;
- writable Forge home;
- storage root;
- aliases path;
- host name;
- available capabilities.

The portable core consumes that explicit environment.

Environment detection belongs to the host.


## Presentation

The portable baseline is intentionally simple:

    forge.render_standard(run)

That produces:

    canonical packet
    +
    small human summary

The canonical packet does not depend on a particular renderer.

A richer host can render the structured run however it wants:

    import forge
    from my_renderer import render

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    render(run)

No large renderer framework is required.


## Pythonista

Forge itself does not depend on Pythonista.

Pythonista is one example of a host environment.

The intended layout is:

    writable Python package directory/
        forge/
        forge_core/
        forge_packages/

    ~/Documents/forge_entry.py

The bootstrap helper:

    bootstrap/pythonista.py

downloads the Portable Forge installer. The installer detects Pythonista,
installs the runtime into `~/Documents/site-packages-3`, creates the small
`~/Documents/forge_entry.py` launcher, and opens it in the editor.

The launcher provides a clipboard-based workflow by default.

Clipboard behaviour is part of the Pythonista adapter, not part of Forge core.


### Existing Forge installations

Pythonista can also contain older Forge layouts such as:

    ~/Documents/forge/

Installing another runtime with the same top-level Python namespaces can
shadow the existing one.

The Pythonista bootstrap therefore checks for conflicting Forge namespaces and
stops before installation when one is found.

Migration should be deliberate rather than silently replacing or shadowing an
existing runtime.

See `adapters/pythonista/` for the Pythonista-specific layer.


## Installation options

Portable Forge supports multiple installation paths.


### Standard-library installer

From a local checkout:

    python install.py --source .

With an explicit package directory:

    python install.py --source . --target /path/to/site-packages

From the stable v0.1.1 release:

    python install.py --github jackatttack/Forge --ref v0.1.1

For deliberate testing of the current development branch:

    python install.py --github jackatttack/Forge --ref main

The installer uses only the Python standard library.


### Bootstrap

Some constrained Python environments make downloading or arranging an entire
repository awkward.

A small environment bootstrap can download `install.py` and invoke it.

See `bootstrap/`.


### Python packaging

Forge is packaged as the Python distribution:

    portable-forge

Install it from PyPI with:

    pip install portable-forge

The Python import remains:

    import forge

The distribution is pure Python and the public package contains the portable
runtime packages `forge`, `forge_core`, and `forge_packages`.


## Repository layout

    .
    |-- README.md
    |-- install.py
    |-- pyproject.toml
    |
    |-- forge/              public Python API and standard host
    |-- forge_core/         portable execution runtime
    |-- forge_packages/     Forge operation packages
    |
    |-- adapters/           environment-specific wrappers
    |-- bootstrap/          environment bootstrap helpers
    |-- docs/               architecture and usage documentation
    |-- examples/           embedding examples
    `-- renderers/          presentation notes and future richer renderers


## Public Python API

The intended public API is small:

    forge.run_text(...)
    forge.render_standard(...)
    forge.make_environment(...)
    forge.standard_environment(...)
    forge.first_boot_text()

Most users should not need to import `forge_core` directly.

See `docs/EMBEDDING.md`.


## Design principles

Forge aims to stay:

- local-first;
- human-in-the-loop;
- pure Python;
- portable;
- inspectable;
- recoverable;
- text-protocol friendly;
- useful in constrained environments;
- understandable by the person who owns the code.

A host can become sophisticated.

The core should remain boring.
## License

Forge is released under the MIT License. See `LICENSE`.


## Project status

This repository is an early portable rebuild of Forge.

The portable release boundary is tested independently from the historical
Pythonista-specific implementation.

The current baseline proves that Forge can:

- run with platform UI physically absent;
- run with clipboard integration physically absent;
- run with editor integration physically absent;
- install without pip;
- execute through a standard Python API;
- operate through a thin host wrapper;
- protect against conflicting Forge namespaces during installation;
- return deterministic packets suitable for a human/AI feedback loop.

The API, compatibility matrix, adapters, packaging, and presentation may still
evolve before a stable 1.0 release.