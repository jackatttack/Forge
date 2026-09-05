# Forge

**Your code is somewhere the AI can't reach. Forge fixes that with the clipboard.**

You're coding with ChatGPT or Claude. The chat can't see your files — it's on an
iPhone, a locked-down work machine, an air-gapped box, or just a normal laptop
where you'd rather not hand an agent the keys.

So you copy and paste. Describe the file, paste the code, get a suggestion back,
find the file, paste it in, run it, copy the error, paste that back. Repeat.

Forge replaces that with two blobs of text.

## One round trip

The assistant sends you a **bundle** — ordinary text on your clipboard:

```
READ billing.py

REPLACE billing.py::calculate_total
BEGIN_BODY
def calculate_total(items):
    return sum(item.price for item in items)
END_BODY

RUN tests/test_billing.py
```

You read it. If you're happy, you run Forge.

Forge hands back a **packet**:

```
=== FORGE RUN ===
Run: 20260905_141203
Mode: dev
Status: APPLIED

Ops:
- APPLIED | READ    | billing.py :: 84 lines
- APPLIED | REPLACE | billing.py::calculate_total :: 6 lines -> 2 lines
- FAILED  | RUN     | tests/test_billing.py :: exit 1

=== OUTPUT ===
FAILED tests/test_billing.py::test_discount
AttributeError: 'Item' object has no attribute 'price'

=== FORGE SUMMARY ===
Status: APPLIED
Ops: 2 applied - 0 skipped - 1 failed
Changed: 1 file
```

You paste that back into the chat.

The assistant now knows the edit landed, knows the test failed, and knows
exactly why — because Forge read your actual file and ran your actual test. It
isn't guessing from your description. It isn't claiming the change worked.

That's Forge. A bundle goes one way, a packet comes back, and the packet is
ground truth.

## Why this matters

The failure mode of long copy-paste sessions is drift. The conversation builds
a picture of your project that slowly stops matching the project. The model
says "I've updated the function" when nothing was updated. It patches a file
whose contents it last saw twenty messages ago.

Forge removes the guessing. Every claim about your code gets checked against
your code.

A failed packet is as useful as a successful one — the next turn starts from a
real traceback instead of a hypothesis.

## You stay in the loop

Forge is not an agent. Nothing runs on your machine because a model suggested
it.

The bundle arrives as plain text and sits there until you act. You read it.
You can edit it before running it — swap the loop for a vector operation,
simplify the approach, drop the ops you don't want. That is exactly the moment
where copy-paste teaches you something, and Forge keeps it.

What Forge takes away is the tedious part: hunting for the file, matching
indentation, pasting into the wrong place, re-typing the error message.

If anything, you see more of the change than before. `DIFF` shows you what
actually landed, and the packet reports every mutation. A paste-and-pray loop
gives you less visibility, not more.

## When you'd reach for it

Forge is worth it when the code lives somewhere an agent can't go:

- Pythonista on iOS — the original reason Forge exists
- machines where you can't install a coding agent
- air-gapped or restricted environments
- any setup where you want the AI to have eyes on the code but no hands on the
  keyboard

If you're already running Claude Code or Cursor against a normal repo on a
normal laptop, you probably don't need Forge.

## The vocabulary

Fifteen operations, deliberately:

| Area                | Operations                                     |
| ------------------- | ---------------------------------------------- |
| Forge itself        | `FORGE`                                        |
| Inspect             | `MAP`, `READ`, `SEARCH`                        |
| Edit                | `WRITE`, `REPLACE`, `INSERT`, `DELETE`, `COPY` |
| Execute and recover | `RUN`, `DIFF`, `REVERT`, `BRANCH`              |
| Utilities           | `URL`, `ALIAS`                                 |

The model doesn't have to memorise them. `FORGE ops` lists them; `FORGE help
REPLACE` explains one. The installed runtime is the documentation.

## Getting started

Copy `FORGE boot` to your clipboard, run Forge, and paste the result into a new
chat. That text teaches the model the protocol and asks it to begin with a
read-only look around. From there the loop is just: bundle out, packet back.

Install instructions below.

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