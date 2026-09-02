# Forge

**A better copy-paste loop for coding with AI.**

If you regularly copy code out of ChatGPT, Claude, or another AI and paste it
into a local project, Forge was made for that workflow.

Forge turns copy and paste into a small coding protocol.

Instead of passing loose snippets back and forth, the AI can send you a plain
text **Forge bundle** that asks your local environment to inspect files, search
code, make edits, run programs, or show what changed.

You run that bundle locally.

Forge does the work and returns a structured **run packet** showing exactly
what happened.

Copy that packet back into the chat and the AI now has real information about
the code on your device.

**The packet is ground truth.**

At its simplest:

    chat
      |
      | copy Forge bundle
      v
    Forge on your device
      |
      | inspect / edit / run
      v
    Forge run packet
      |
      | copy back
      v
    chat

For a clipboard-driven environment such as Pythonista:

**Python + clipboard + chat + Forge gives you a robust local coding loop.**


## Why Forge exists

Coding with an AI in a normal chat window is useful, but the manual loop gets
old quickly:

    ask -> copy code -> find file -> paste -> run -> copy result -> paste back

Then repeat.

Forge tightens that loop.

Instead of copying loose code fragments, you can copy a small set of explicit
operations:

    READ app.py

    REPLACE app.py::calculate_total
    BEGIN_BODY
    def calculate_total(items):
        return sum(item.price for item in items)
    END_BODY

    RUN tests.py

Forge performs those operations locally and tells the chat what actually
happened.

So the loop becomes:

    chat -> copy bundle -> Forge -> copy packet -> chat

That means less file hunting, less repeated context explaining, and fewer
moments where the conversation and the real project silently drift apart.


## Give the chat eyes into your environment

Forge is not only about writing code.

It gives an AI conversation a simple way to inspect an environment it cannot
normally see.

For example:

    MAP .

    SEARCH . FOR "calculate_total"

    READ app.py

You copy the bundle, run Forge, and paste the resulting packet back.

The AI can now reason from the real project structure and real file contents
instead of relying on your description of them.

In a clipboard-based setup, the clipboard becomes a tiny text tool channel
between the chat and your machine.

No special tool integration from the AI provider is required.

If the model can produce text and understand the text you return, it can work
through Forge.


## The idea in 60 seconds

The assistant proposes a Forge bundle.

You decide whether to run it.

Forge parses the whole bundle first, validates it, executes it against the
local project, records what happened, and produces a deterministic run packet.

That packet is what makes the copy-paste loop robust.

The chat does not have to guess whether a file changed or whether some code
actually ran. Forge reports the result.

    The assistant proposes.
    The user runs.
    Forge reports.
    The packet confirms.


## A first Forge loop

Suppose the AI has no idea what is in your project yet.

It might start with:

    MAP .
    DEPTH: 2

    FORGE ops

Save that bundle to a file and run:

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

Paste that packet back into the chat.

The assistant now has grounded information about the environment and can decide
what to inspect next.

Nothing changed merely because the assistant suggested it.


## Pythonista: one-copy install

Pythonista is where Forge started, and it remains one of the cleanest examples
of the clipboard loop.

For a clean Pythonista installation, create any temporary Python script, paste
the following code into it, and run it once:

    import urllib.request

    url = (
        'https://raw.githubusercontent.com/'
        'jackatttack/Forge/main/bootstrap/pythonista.py'
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

It installs Portable Forge into `~/Documents/site-packages-3/forge` and creates:

    ~/Documents/forge_entry.py

The Pythonista console UI is packaged inside Forge at
`forge.adapters.pythonista.console_ui`; no separate root renderer is required.

On first install, `forge_entry.py` opens in Pythonista ready to use.

### Start a new AI session

Forge can teach the model how to use Forge.

Copy this onto the clipboard:

    FORGE boot

Run `forge_entry.py`, then paste the returned `FORGE FIRST BOOT` text into
ChatGPT, Claude, or another LLM.

That guide tells the model how the Forge loop works and asks it to begin with
a small read-only orientation bundle:

    MAP .
    DEPTH: 2

    FORGE ops

The model gives you that bundle. Run it with `forge_entry.py` and paste the
returned packet back into the conversation.

From there, the normal loop is simply:

    1. The model gives you a Forge bundle.
    2. Run `forge_entry.py`.
    3. Forge works against your Pythonista Documents folder.
    4. The result goes back onto the clipboard.
    5. Paste it into the conversation.
    6. Repeat.

No special AI integration is required. `FORGE boot` gives a new conversation
the protocol it needs, and the returned run packets keep the conversation
grounded in what actually happened on your machine.

That is the workflow Forge was originally built to make tighter.


## What Forge can do

Forge can:

- inspect directory structure;
- read files;
- search projects;
- create and edit text files;
- make targeted Python edits;
- copy and delete project content;
- run local Python code;
- show what changed;
- record and recover changes;
- create filesystem checkpoints;
- work with URLs;
- provide reusable aliases.

The model does not need to memorise the command language.

Ask the installed runtime:

    FORGE ops

For help with one operation:

    FORGE help WRITE

For deeper help:

    FORGE help WRITE full


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

Host environments can add their own extensions without expanding the portable
core.

Detailed syntax belongs to the installed help system rather than this README.


## A typical working session

A good Forge session is inspect-first:

    MAP path/to/area

    SEARCH path/to/area FOR "thing_to_find"

    READ path/to/file.py

    REPLACE path/to/file.py::target
    BEGIN_BODY
    ...
    END_BODY

    RUN relevant_test.py

    DIFF current

The pattern matters more than the exact operation:

    inspect
        ->
    make a small grounded change
        ->
    run or verify it
        ->
    inspect the packet
        ->
    decide what happens next


## The packet is the contract

Forge separates execution from claims about execution.

An AI can suggest anything it wants.

Until you run the bundle, nothing has happened locally.

After the run, the packet records the result.

Successful packets confirm what Forge actually did.

Failed packets are useful too: they give the next turn concrete evidence
instead of forcing the assistant to guess.

That makes long copy-paste sessions much less fragile.


## What Forge is - and what it is not

Forge is a local execution protocol and runtime.

It is not tied to a particular AI company.

It is not tied to a particular editor.

It does not require the AI provider to expose tool calling, filesystem access,
or a coding-agent API.

The AI produces ordinary text.

The user chooses whether to run it.

Forge executes it locally and returns ordinary text.

Forge does not need to replace your chat app.

It sits between the chat you already use and the code you already have.


## Other ways to run Forge

The clipboard loop is only one host.

Forge can also run from a terminal:

    python -m forge bundle.txt

or from stdin:

    python -m forge < bundle.txt

It can also be embedded in another Python program:

    import forge

    run = forge.run_text(
        bundle,
        project_root="/path/to/project",
    )

    result = forge.render_standard(run)

That means a clipboard launcher, terminal, editor extension, GUI, web view, or
another transport can all sit around the same portable runtime.


## Installation options

### PyPI

Forge is distributed as:

    portable-forge

Install it with:

    pip install portable-forge

The Python import remains:

    import forge


### Local checkout

Portable Forge includes a standard-library-only installer:

    python install.py --source .


### GitHub source

Install from the stable v0.1.1 release:

    python install.py --github jackatttack/Forge --ref v0.1.1

Or deliberately install the current development branch:

    python install.py --github jackatttack/Forge --ref main

The installer protects existing Python packages from accidental namespace collisions.

For the full installation guide, see
[docs/INSTALLING.md](docs/INSTALLING.md).


## Safety model

Forge can edit and execute local project code, so its boundaries are explicit.

The complete bundle is parsed before execution, project operations stay inside
an explicit project root, mutations are reported, and recovery information is
recorded where appropriate.

The user or host still decides when a bundle is actually run.

For the full model, see [docs/SAFETY.md](docs/SAFETY.md).


## Portable core and host adapters

Forge itself does not depend on Pythonista, a clipboard API, a UI toolkit, or
a particular operating system.

Environment-specific behaviour lives in small host adapters around the
portable runtime.

The central rule is:

**Adapters import Forge. Forge never imports adapters.**

For the architecture and host contract, see
[docs/HOST_ADAPTERS.md](docs/HOST_ADAPTERS.md).


## Pythonista

Pythonista is the original Forge host and the reason the clipboard workflow
exists.

Its adapter provides clipboard input/output and richer console presentation
around the portable core.

The one-copy bootstrap above is the recommended starting point.

See [adapters/pythonista/](adapters/pythonista/) for the host-specific layer.


## Public Python API

The intended Python API is deliberately small:

    forge.run_text(...)
    forge.render_standard(...)
    forge.make_environment(...)
    forge.standard_environment(...)
    forge.first_boot_text()

Most users should never need to import `forge.core` or `forge.packages`
directly.

For embedding examples, see [docs/EMBEDDING.md](docs/EMBEDDING.md).


## Learn more

The README is the front door.

The deeper technical material lives in the docs:

- [How Forge works](docs/HOW_FORGE_WORKS.md)
- [Installing Forge](docs/INSTALLING.md)
- [Safety model](docs/SAFETY.md)
- [Host adapters](docs/HOST_ADAPTERS.md)
- [Embedding Forge](docs/EMBEDDING.md)

The installed runtime is also part of the documentation:

    FORGE ops

    FORGE help <OP>

    FORGE help <OP> full


## Project status

Forge is an early portable project built out of a real daily AI coding
workflow.

It began as a way to make coding with a chat model on an iPhone dramatically
less tedious, then grew into a portable text protocol that can sit behind
different Python environments and host interfaces.

The API, adapters, packaging, and presentation may continue to evolve before a
stable 1.0 release.


## License

Forge is released under the MIT License. See [LICENSE](LICENSE).