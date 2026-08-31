# -*- coding: utf-8 -*-
"""
Resolved Forge environment context.

This module normalises environmental facts supplied by a host adapter.

It deliberately performs no host/platform detection.
"""

import os


def _required_path(value, name):
    value = str(value or '').strip()

    if not value:
        raise ValueError(
            'Forge environment requires %s'
            % name
        )

    return os.path.abspath(value)


def make_environment(
    project_root,
    forge_home,
    storage_root=None,
    aliases_path=None,
    capabilities=None,
    host='plain',
    storage=None,
    features=None,
    config_path=None,
):
    """Build one normalised environment dictionary."""
    project_root = _required_path(
        project_root,
        'project_root',
    )

    forge_home = _required_path(
        forge_home,
        'forge_home',
    )

    if storage_root:
        storage_root = os.path.abspath(
            str(storage_root)
        )
    else:
        storage_root = os.path.join(
            forge_home,
            'artifacts',
        )

    if aliases_path:
        aliases_path = os.path.abspath(
            str(aliases_path)
        )
    else:
        aliases_path = os.path.join(
            forge_home,
            'aliases.json',
        )

    caps = capabilities or {}

    if not isinstance(
        caps,
        dict,
    ):
        raise ValueError(
            'Forge environment capabilities must be a dict'
        )

    storage_settings = storage or {}

    if not isinstance(
        storage_settings,
        dict,
    ):
        raise ValueError(
            'Forge environment storage settings must be a dict'
        )

    feature_settings = features or {}

    if not isinstance(
        feature_settings,
        dict,
    ):
        raise ValueError(
            'Forge environment features must be a dict'
        )

    resolved_config_path = str(
        config_path
        or ''
    ).strip()

    if resolved_config_path:
        resolved_config_path = os.path.abspath(
            resolved_config_path
        )

    return {
        'host': str(
            host
            or 'plain'
        ),
        'project_root': project_root,
        'forge_home': forge_home,
        'storage_root': storage_root,
        'aliases_path': aliases_path,
        'storage': dict(
            storage_settings
        ),
        'features': dict(
            feature_settings
        ),
        'capabilities': dict(
            caps
        ),
        'config_path': resolved_config_path,
    }


def normalise_environment(
    environment=None,
    project_root=None,
    forge_home=None,
    capabilities=None,
    host=None,
    storage=None,
    features=None,
    config_path=None,
):
    """Return one complete environment from explicit supplied facts."""
    source = dict(
        environment
        or {}
    )

    caps = dict(
        source.get(
            'capabilities'
        )
        or {}
    )

    if capabilities:
        if not isinstance(
            capabilities,
            dict,
        ):
            raise ValueError(
                'Forge environment capabilities must be a dict'
            )

        caps.update(
            capabilities
        )

    storage_settings = dict(
        source.get(
            'storage'
        )
        or {}
    )

    if storage:
        if not isinstance(
            storage,
            dict,
        ):
            raise ValueError(
                'Forge environment storage settings must be a dict'
            )

        storage_settings.update(
            storage
        )

    feature_settings = dict(
        source.get(
            'features'
        )
        or {}
    )

    if features:
        if not isinstance(
            features,
            dict,
        ):
            raise ValueError(
                'Forge environment features must be a dict'
            )

        feature_settings.update(
            features
        )

    return make_environment(
        project_root=(
            project_root
            or source.get(
                'project_root'
            )
        ),

        forge_home=(
            forge_home
            or source.get(
                'forge_home'
            )
        ),

        storage_root=source.get(
            'storage_root'
        ),

        aliases_path=source.get(
            'aliases_path'
        ),

        capabilities=caps,

        host=(
            host
            or source.get(
                'host'
            )
            or 'plain'
        ),

        storage=storage_settings,

        features=feature_settings,

        config_path=(
            config_path
            or source.get(
                'config_path'
            )
        ),
    )


def from_ctx(ctx):
    """Return the resolved environment attached to an op context."""
    environment = (
        (ctx or {}).get('environment')
        or {}
    )

    return environment

def path_from_ctx(ctx, name):
    """Return one required absolute path from resolved Forge context."""
    name = str(name or '').strip()

    if not name:
        raise ValueError(
            'Forge environment path name is required.'
        )

    environment = from_ctx(
        ctx
    )

    value = environment.get(
        name
    )

    # Transitional compatibility for existing ops while the public ctx field
    # still exists. There is deliberately no cwd or host fallback.
    if (
        not value
        and name == 'project_root'
    ):
        value = (
            (ctx or {}).get(
                'project_root'
            )
        )

    value = str(
        value
        or ''
    ).strip()

    if not value:
        raise ValueError(
            'Forge requires explicit environment[%r].'
            % name
        )

    return os.path.abspath(
        value
    )


def capability(ctx, name, default=False):
    """Return one optional host capability from an op context."""
    environment = from_ctx(ctx)

    capabilities = (
        environment.get('capabilities')
        or {}
    )

    return capabilities.get(
        str(name),
        default,
    )