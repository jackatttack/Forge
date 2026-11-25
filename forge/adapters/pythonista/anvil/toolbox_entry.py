"""Anvil's card in the Toolbox hub: Toolbox/tools/forge.json.

Role: store · Part of: anvil/toolbox

    toolbox_entry.ensure()     write it when missing (each run Anvil shows)
    toolbox_entry.write()      write it now (the installer)

The card opens this copy of Anvil: its module path comes from the package
Anvil was imported as (anvil.tool for a personal install,
forge.adapters.pythonista.anvil.tool for the copy that ships with Forge).
Nothing is written when the Toolbox is not installed.
"""
import json
import os

TOOLBOX = os.path.expanduser('~/Documents/Toolbox')
MANIFEST = os.path.join(TOOLBOX, 'tools', 'forge.json')
PACKAGE = __name__.rsplit('.', 1)[0]     # 'anvil' or 'forge.adapters.pythonista.anvil'


def card():
    return {
        'name': 'Forge',
        'emoji': '🔨',
        'what': 'Forge runs',
        'module': PACKAGE + '.tool',
        'function': 'main',
        'about': 'Forge runs as cards: the verdict, what changed, each operation '
                 'and its output, recent runs, and controls that copy a resume or '
                 'revert bundle.',
    }


def write():
    """Write the card now (through a temporary file). Returns its path."""
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    temporary = MANIFEST + '.anvil-tmp'
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(card(), handle, indent=2)
    os.replace(temporary, MANIFEST)
    return MANIFEST


def ensure():
    """Write the card when the Toolbox is here and has no Anvil card yet.
    Never raises: a missing card never stops a run from showing."""
    try:
        if os.path.isdir(TOOLBOX) and not os.path.isfile(MANIFEST):
            write()
    except Exception:
        pass