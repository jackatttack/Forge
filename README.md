# Forge

**Your code is somewhere the AI can't reach. Forge fixes that with the clipboard.**

You're coding with ChatGPT or Claude. The chat can't see your files — it's on an
iPhone, a locked-down work machine, or an air-gapped box.

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

Forge hands back a **packet**.

For the README demo we ran the same idea in a disposable
`scratch/readme_demo/` folder. This is a shortened excerpt from the real failing
Forge packet:

```
=== FORGE RUN ===
Run: 20260905_192043
Mode: dev
Status: FAILED

Errors:
- FAILED_RUNTIME | RUN :: Script exited with code 1

Ops:
- APPLIED | READ | scratch/readme_demo/billing.py :: Lines 1-10
- APPLIED | REPLACE | scratch/readme_demo/billing.py::calculate_total :: Replaced scratch/readme_demo/billing.py::calculate_total lines 6-10
- FAILED_RUNTIME | RUN | scratch/readme_demo/tests/test_billing.py :: Script exited with code 1

Changed files:
- scratch/readme_demo/billing.py — modified · 10 -> 7 lines

=== PREVIEW ===
...
AttributeError: 'Item' object has no attribute 'price'

=== FORGE SUMMARY ===
Status: FAILED
Ops: 2 applied · 0 skipped · 1 failed
Changed: 1 file
Packet: 2.3 KB
Errors: 1
```

You paste that back into the chat.

The assistant now knows the edit landed and has the real test failure to reason
from — because Forge read your actual file and ran your actual test. It isn't
guessing from your description. It isn't claiming the change worked.

That's Forge. A bundle goes one way, a packet comes back, and the packet is
ground truth.

## Why this matters

The failure mode of long copy-paste sessions is drift. The conversation builds
a picture of your project that slowly stops matching the project. The model
says "I've updated the function" when nothing was updated. It patches a file
whose contents it last saw twenty messages ago.

Forge removes the guessing. Claims about what Forge read, changed, or ran are
checked against the real project and reported in the packet.

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

## What a session looks like

One round trip is the unit. A working session is several of them, and it goes
best inspect-first:

```
MAP path/to/area

SEARCH path/to/area FOR "thing_to_find"

READ path/to/file.py

REPLACE path/to/file.py::target
BEGIN_BODY
...
END_BODY

RUN relevant_test.py

DIFF current
```

The pattern matters more than the exact operations:

```
inspect
    ->
make a small grounded change
    ->
run or verify it
    ->
read the packet
    ->
decide what happens next
```

The early ops don't mutate your project — `MAP`, `SEARCH`, and `READ` are
read-only. Letting the assistant look before it edits is what keeps the rest of
the session grounded.

## When you'd reach for it

Forge is worth it when the code lives somewhere an agent can't go:

- Pythonista on iOS — the original reason Forge exists
- machines where you can't install a coding agent
- air-gapped or restricted environments
- any setup where you want the AI to have eyes on the code but no hands on
  the keyboard

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

Host environments can add their own extensions without expanding the portable
core.

## Pythonista: one-copy install

Pythonista is where Forge started, and it remains the cleanest example of the
clipboard loop.

Create any temporary Python script, paste the following into it, and run it
once:

```
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
```

That is the whole bootstrap.

It installs Portable Forge into `~/Documents/site-packages-3/forge` and creates:

```
~/Documents/forge_entry.py
```

The Pythonista console UI is packaged inside Forge at
`forge.adapters.pythonista.console_ui`; no separate root renderer is required.

On first install, `forge_entry.py` opens in Pythonista ready to use.

### Starting a new AI session

Forge can teach the model how to use Forge.

Copy this onto the clipboard:

```
FORGE boot
```

Run `forge_entry.py`, then paste the returned `FORGE FIRST BOOT` text into
ChatGPT, Claude, or another LLM.

That guide tells the model how the Forge loop works and asks it to begin with
a small read-only orientation bundle:

```
MAP .
DEPTH: 2

FORGE ops
```

The model gives you that bundle. Run it with `forge_entry.py` and paste the
returned packet back into the conversation.

From there, the normal loop is simply:

```
1. The model gives you a Forge bundle.
2. Run `forge_entry.py`.
3. Forge works against your Pythonista Documents folder.
4. The result goes back onto the clipboard.
5. Paste it into the conversation.
6. Repeat.
```

No special AI integration is required. If the model can produce text and read
the text you return, it can work through Forge.

## Other ways to run Forge

The clipboard loop is only one host.

Forge can also run from a terminal:

```
python -m forge bundle.txt
```

or from stdin:

```
python -m forge < bundle.txt
```

It can also be embedded in another Python program:

```
import forge

run = forge.run_text(
    bundle,
    project_root="/path/to/project",
)

result = forge.render_standard(run)
```

That means a clipboard launcher, terminal, editor extension, GUI, web view, or
another transport can all sit around the same portable runtime.

## Installation options

### PyPI

Forge is distributed as:

```
portable-forge
```

Install it with:

```
pip install portable-forge
```

The Python import remains:

```
import forge
```

### Local checkout

Portable Forge includes a standard-library-only installer:

```
python install.py --source .
```

### GitHub source

Install from the stable v0.1.2 release:

```
python install.py --github jackatttack/Forge --ref v0.1.2
```

Or deliberately install the current development branch:

```
python install.py --github jackatttack/Forge --ref main
```

The installer protects existing Python packages from accidental namespace
collisions.

For the full installation guide, see [docs/INSTALLING.md](docs/INSTALLING.md).

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

Environment-specific behaviour lives in small host adapters around the portable
runtime.

The central rule is:

**Adapters import Forge. Forge never imports adapters.**

For the architecture and host contract, see
[docs/HOST_ADAPTERS.md](docs/HOST_ADAPTERS.md).

## Public Python API

The intended Python API is deliberately small:

```
forge.run_text(...)
forge.render_standard(...)
forge.make_environment(...)
forge.standard_environment(...)
forge.first_boot_text()
```

Most users should never need to import `forge.core` or `forge.packages`
directly.

For embedding examples, see [docs/EMBEDDING.md](docs/EMBEDDING.md).

## Learn more

The README is the front door. The deeper technical material lives in the docs:

- [How Forge works](docs/HOW_FORGE_WORKS.md)
- [Installing Forge](docs/INSTALLING.md)
- [Safety model](docs/SAFETY.md)
- [Host adapters](docs/HOST_ADAPTERS.md)
- [Embedding Forge](docs/EMBEDDING.md)

The installed runtime is also part of the documentation:

```
FORGE ops

FORGE help <OP>

FORGE help <OP> full
```

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