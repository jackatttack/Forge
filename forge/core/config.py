# -*- coding: utf-8 -*-
"""
Portable Forge configuration.

This module reads and validates forge.json.

It performs no host detection:
- no cwd lookup
- no environment-variable lookup
- no platform imports

Relative config paths are resolved against an explicitly supplied forge_home.
"""

import copy
import json
import os


CONFIG_VERSION = 1


DEFAULT_CONFIG = {
    'config_version': CONFIG_VERSION,

    'paths': {
        'default_project_root': '..',
        'storage_root': 'artifacts',
        'aliases_path': 'aliases.json',
    },

    'storage': {
        'max_runs': 100,
    },

    'features': {},

    # Additional named filesystem roots, as {name: path}. Paths are
    # resolved like other config paths: absolute paths are used as given,
    # relative paths resolve against forge_home. Empty by default, so
    # Forge resolves every path against project_root unless the user
    # deliberately configures otherwise.
    'roots': {},
}


def default_config():
    """Return an independent copy of Forge's built-in defaults."""
    return copy.deepcopy(
        DEFAULT_CONFIG
    )


def config_path(
    forge_home,
    path=None,
):
    """Return the absolute Forge config path."""
    home = str(
        forge_home
        or ''
    ).strip()

    if not home:
        raise ValueError(
            'Forge config requires forge_home.'
        )

    home = os.path.abspath(
        home
    )

    explicit = str(
        path
        or ''
    ).strip()

    if not explicit:
        return os.path.join(
            home,
            'forge.json',
        )

    if os.path.isabs(
        explicit
    ):
        return os.path.abspath(
            explicit
        )

    return os.path.abspath(
        os.path.join(
            home,
            explicit,
        )
    )


def _merge(base, incoming):
    out = copy.deepcopy(
        base
    )

    for key, value in (
        incoming
        or {}
    ).items():
        if (
            isinstance(
                value,
                dict,
            )
            and isinstance(
                out.get(key),
                dict,
            )
        ):
            out[key] = _merge(
                out[key],
                value,
            )
        else:
            out[key] = copy.deepcopy(
                value
            )

    return out


def _validate_paths(paths):
    if not isinstance(
        paths,
        dict,
    ):
        raise ValueError(
            'Forge config "paths" must be an object.'
        )

    allowed = {
        'default_project_root',
        'storage_root',
        'aliases_path',
    }

    unknown = set(
        paths
    ) - allowed

    if unknown:
        raise ValueError(
            'Unknown Forge config path setting(s): %s'
            % ', '.join(
                sorted(unknown)
            )
        )

    for key in allowed:
        value = paths.get(
            key
        )

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                'Forge config paths.%s must be a string.'
                % key
            )

        if not value.strip():
            raise ValueError(
                'Forge config paths.%s cannot be empty.'
                % key
            )


def _validate_storage(storage):
    if not isinstance(
        storage,
        dict,
    ):
        raise ValueError(
            'Forge config "storage" must be an object.'
        )

    unknown = set(
        storage
    ) - {'max_runs'}

    if unknown:
        raise ValueError(
            'Unknown Forge storage setting(s): %s'
            % ', '.join(
                sorted(unknown)
            )
        )

    value = storage.get(
        'max_runs'
    )

    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            'Forge config storage.max_runs must be an integer.'
        )

    try:
        value = int(
            value
        )
    except Exception:
        raise ValueError(
            'Forge config storage.max_runs must be an integer.'
        )

    if value < 1:
        raise ValueError(
            'Forge config storage.max_runs must be at least 1.'
        )

    storage['max_runs'] = value


def _validate_features(features):
    if not isinstance(
        features,
        dict,
    ):
        raise ValueError(
            'Forge config "features" must be an object.'
        )

    for name, value in features.items():
        if not isinstance(
            value,
            bool,
        ):
            raise ValueError(
                'Forge config feature %r must be true or false.'
                % str(name)
            )

def _validate_roots(roots):
    """
    Validate the optional named-roots mapping.

    Root names become a path prefix ("icloud:tools/app.py"), so a name
    containing a separator or colon would be unparseable. Rejecting it
    here gives a clear configuration error instead of a confusing
    unknown-root failure later.
    """
    if not isinstance(
        roots,
        dict,
    ):
        raise ValueError(
            'Forge config "roots" must be an object.'
        )

    for name, value in roots.items():
        name = str(name)

        if not name.strip():
            raise ValueError(
                'Forge config root names cannot be empty.'
            )

        if (
            ':' in name
            or '/' in name
            or os.sep in name
        ):
            raise ValueError(
                'Forge config root name %r cannot contain ":" or a path '
                'separator.'
                % name
            )

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                'Forge config root %r must be a string path.'
                % name
            )

        if not value.strip():
            raise ValueError(
                'Forge config root %r cannot be empty.'
                % name
            )


def normalise_config(config=None):
    """Merge supplied config over defaults and validate version 1."""
    incoming = dict(
        config
        or {}
    )

    allowed_top = {
        'config_version',
        'paths',
        'storage',
        'features',
        'roots',
    }

    unknown = set(
        incoming
    ) - allowed_top

    if unknown:
        raise ValueError(
            'Unknown Forge config setting(s): %s'
            % ', '.join(
                sorted(unknown)
            )
        )

    merged = _merge(
        default_config(),
        incoming,
    )

    version = merged.get(
        'config_version'
    )

    if version != CONFIG_VERSION:
        raise ValueError(
            'Unsupported Forge config_version %r; expected %d.'
            % (
                version,
                CONFIG_VERSION,
            )
        )

    _validate_paths(
        merged['paths']
    )

    _validate_storage(
        merged['storage']
    )

    _validate_features(
        merged['features']
    )

    _validate_roots(
        merged['roots']
    )

    return merged


def load_config(
    forge_home,
    path=None,
):
    """
    Load forge.json.

    A missing file is not an error; built-in defaults are returned.
    An existing malformed or invalid config fails clearly.
    """
    actual = config_path(
        forge_home,
        path=path,
    )

    if not os.path.isfile(
        actual
    ):
        return default_config()

    try:
        with open(
            actual,
            'r',
            encoding='utf-8',
        ) as f:
            raw = json.load(f)
    except Exception as e:
        raise ValueError(
            'Forge config unreadable: %s: %s'
            % (
                type(e).__name__,
                e,
            )
        )

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            'Forge config root must be a JSON object.'
        )

    return normalise_config(
        raw
    )


def _resolve_path(
    forge_home,
    value,
):
    value = str(
        value
        or ''
    ).strip()

    if os.path.isabs(
        value
    ):
        return os.path.abspath(
            value
        )

    return os.path.abspath(
        os.path.join(
            forge_home,
            value,
        )
    )


def resolve_config(
    config,
    forge_home,
    path=None,
):
    """Resolve one validated config into absolute runtime settings."""
    raw_home = str(
        forge_home
        or ''
    ).strip()

    if not raw_home:
        raise ValueError(
            'Forge config resolution requires forge_home.'
        )

    home = os.path.abspath(
        raw_home
    )

    config = normalise_config(
        config
    )

    paths = config[
        'paths'
    ]

    return {
        'config_path': config_path(
            home,
            path=path,
        ),

        'default_project_root': _resolve_path(
            home,
            paths[
                'default_project_root'
            ],
        ),

        'storage_root': _resolve_path(
            home,
            paths[
                'storage_root'
            ],
        ),

        'aliases_path': _resolve_path(
            home,
            paths[
                'aliases_path'
            ],
        ),

        'storage': dict(
            config[
                'storage'
            ]
        ),

        'features': dict(
            config[
                'features'
            ]
        ),

        # Named roots resolve like every other config path: absolute as
        # given, relative against forge_home.
        'roots': {
            str(name): _resolve_path(
                home,
                value,
            )
            for name, value in config[
                'roots'
            ].items()
        },
    }
