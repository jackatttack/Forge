# -*- coding: utf-8 -*-
"""
Portable Forge alias persistence.

This module owns where aliases are read and written.

It performs no host detection:
- no ~/Documents
- no cwd lookup
- no environment-variable lookup
- no Pythonista assumptions

The resolved Forge environment is the canonical source of aliases_path.
Explicit project_root / forge_home arguments remain as compatibility inputs.
"""

import json
import os


def aliases_path(
    environment=None,
    project_root=None,
    forge_home=None,
):
    """Return the resolved aliases.json path from explicit facts."""
    environment = dict(
        environment
        or {}
    )

    explicit = str(
        environment.get('aliases_path')
        or ''
    ).strip()

    if explicit:
        return os.path.abspath(
            explicit
        )

    home = str(
        forge_home
        or environment.get('forge_home')
        or ''
    ).strip()

    if home:
        return os.path.join(
            os.path.abspath(home),
            'aliases.json',
        )

    root = str(
        project_root
        or environment.get('project_root')
        or ''
    ).strip()

    if not root:
        raise ValueError(
            'Alias storage requires aliases_path, forge_home, or project_root.'
        )

    root = os.path.abspath(
        root
    )

    # Compatibility with historical direct-library callers.
    # This is explicit path derivation, not host detection.
    if os.path.basename(
        root.rstrip(os.sep)
    ) == 'forge':
        return os.path.join(
            root,
            'aliases.json',
        )

    return os.path.join(
        root,
        'forge',
        'aliases.json',
    )


def normalise_aliases(data):
    """Return aliases in the canonical dictionary-entry representation."""
    if not isinstance(
        data,
        dict,
    ):
        return {}

    normalised = {}

    for name, value in data.items():
        name = str(name)

        if isinstance(
            value,
            str,
        ):
            normalised[name] = {
                'expansion': value,
                'tag': None,
                'args': [],
                'description': '',
            }
            continue

        if not isinstance(
            value,
            dict,
        ):
            continue

        entry = dict(value)

        entry['expansion'] = str(
            entry.get('expansion')
            or ''
        )

        entry.setdefault(
            'tag',
            None,
        )

        entry.setdefault(
            'args',
            [],
        )

        entry.setdefault(
            'description',
            '',
        )

        if not isinstance(
            entry.get('args'),
            list,
        ):
            entry['args'] = []

        normalised[name] = entry

    return normalised


def load_aliases(
    environment=None,
    project_root=None,
    forge_home=None,
):
    """Load aliases from the resolved alias file."""
    path = aliases_path(
        environment=environment,
        project_root=project_root,
        forge_home=forge_home,
    )

    if not os.path.isfile(
        path
    ):
        return {}

    try:
        with open(
            path,
            'r',
            encoding='utf-8',
        ) as f:
            data = json.load(f)
    except Exception:
        return {}

    return normalise_aliases(
        data
    )


def save_aliases(
    aliases,
    environment=None,
    project_root=None,
    forge_home=None,
):
    """Persist aliases to the resolved alias file."""
    path = aliases_path(
        environment=environment,
        project_root=project_root,
        forge_home=forge_home,
    )

    parent = os.path.dirname(
        path
    )

    if (
        parent
        and not os.path.isdir(
            parent
        )
    ):
        os.makedirs(
            parent
        )

    data = normalise_aliases(
        aliases
        or {}
    )

    with open(
        path,
        'w',
        encoding='utf-8',
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        f.write('\n')

    return path