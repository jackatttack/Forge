# -*- coding: utf-8 -*-
"""
Package-shaped op registry for Forge.

Discovers ops from:

    forge_packages/core_ops/<name>/op.py
    forge_packages/custom_ops/<name>/op.py

Installed packages are discovered through Python's import machinery so Forge
works both from normal directories and directly from ZIP/wheel importers.

A filesystem fallback is retained for development/custom operation folders
that are not importable as ordinary packages.
"""

import importlib
import importlib.util
import os
import pkgutil
import sys

try:
    from importlib import resources as importlib_resources
except ImportError:
    importlib_resources = None


OPS_BY_NAME = {}
OP_SPECS = {}
OP_MODULES = []
OP_PACKAGE_PATHS = {}
OP_PACKAGE_KINDS = {}
OP_PACKAGE_MODULES = {}


def _root_dir():
    return os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )


def _ops_roots():
    base = os.path.join(
        _root_dir(),
        'forge_packages',
    )

    return [
        (
            'core_ops',
            'forge_packages.core_ops',
            os.path.join(
                base,
                'core_ops',
            ),
        ),
        (
            'custom_ops',
            'forge_packages.custom_ops',
            os.path.join(
                base,
                'custom_ops',
            ),
        ),
    ]


def _safe_module_part(value):
    text = str(
        value
        or ''
    ).strip().lower()

    out = []

    for ch in text:
        if ch.isalnum() or ch == '_':
            out.append(ch)
        else:
            out.append('_')

    return ''.join(out) or 'op'


def _valid_package_part(value):
    text = str(
        value
        or ''
    ).strip()

    return bool(
        text
        and text.isidentifier()
        and not text.startswith('_')
    )


def _resource_package_names(root_module):
    names = set()

    try:
        package = importlib.import_module(
            root_module
        )
    except Exception:
        return names

    if importlib_resources is not None:
        files_fn = getattr(
            importlib_resources,
            'files',
            None,
        )

        if callable(files_fn):
            try:
                root = files_fn(
                    package
                )

                for item in root.iterdir():
                    try:
                        is_dir = item.is_dir()
                    except Exception:
                        is_dir = False

                    name = getattr(
                        item,
                        'name',
                        '',
                    )

                    if (
                        is_dir
                        and _valid_package_part(
                            name
                        )
                    ):
                        names.add(
                            name
                        )
            except Exception:
                pass

        else:
            try:
                for name in importlib_resources.contents(
                    package
                ):
                    if _valid_package_part(
                        name
                    ):
                        names.add(
                            name
                        )
            except Exception:
                pass

    try:
        paths = getattr(
            package,
            '__path__',
            [],
        )

        for info in pkgutil.iter_modules(
            paths
        ):
            name = getattr(
                info,
                'name',
                '',
            )

            if _valid_package_part(
                name
            ):
                names.add(
                    name
                )
    except Exception:
        pass

    return names


def _filesystem_package_names(root):
    names = set()

    if not os.path.isdir(
        root
    ):
        return names

    try:
        children = os.listdir(
            root
        )
    except Exception:
        children = []

    for name in children:
        if not _valid_package_part(
            name
        ):
            continue

        package_dir = os.path.join(
            root,
            name,
        )

        path = os.path.join(
            package_dir,
            'op.py',
        )

        if os.path.isfile(
            path
        ):
            names.add(
                name
            )

    return names


def _physical_package_path(
    package_module,
    fallback='',
):
    if package_module:
        try:
            package = importlib.import_module(
                package_module
            )
        except Exception:
            package = None

        if package is not None:
            source = getattr(
                package,
                '__file__',
                '',
            ) or ''

            if source:
                candidate = os.path.dirname(
                    os.path.abspath(
                        source
                    )
                )

                if os.path.isdir(
                    candidate
                ):
                    return candidate

            for candidate in (
                getattr(
                    package,
                    '__path__',
                    [],
                )
                or []
            ):
                if os.path.isdir(
                    candidate
                ):
                    return os.path.abspath(
                        candidate
                    )

    if (
        fallback
        and os.path.isdir(
            fallback
        )
    ):
        return os.path.abspath(
            fallback
        )

    return ''


def _load_importable_op(
    root_module,
    package_name,
):
    package_module = (
        root_module
        + '.'
        + package_name
    )

    module_name = (
        package_module
        + '.op'
    )

    try:
        mod = importlib.import_module(
            module_name
        )
    except Exception as exc:
        return (
            None,
            (
                '%s: %s'
                % (
                    type(exc).__name__,
                    exc,
                )
            ),
            package_module,
        )

    return (
        mod,
        None,
        package_module,
    )


def _load_filesystem_op(
    path,
    root_kind,
    package_name,
):
    mod_name = (
        'forge_op_%s_%s'
        % (
            _safe_module_part(
                root_kind
            ),
            _safe_module_part(
                package_name
            ),
        )
    )

    spec = importlib.util.spec_from_file_location(
        mod_name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        return (
            None,
            'could not create import spec',
        )

    mod = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        mod_name
    ] = mod

    spec.loader.exec_module(
        mod
    )

    return (
        mod,
        None,
    )


def _register_op(
    mod,
    root_kind,
    package_name,
    package_module,
    package_dir,
):
    label = (
        '%s/%s'
        % (
            root_kind,
            package_name,
        )
    )

    spec = getattr(
        mod,
        'SPEC',
        None,
    )

    if (
        not isinstance(
            spec,
            dict,
        )
        or not spec.get(
            'name'
        )
    ):
        print(
            '[forge registry] %s has no valid SPEC'
            % label,
            file=sys.stderr,
        )
        return False

    op_name = str(
        spec.get(
            'name'
        )
    ).upper()

    if op_name in OPS_BY_NAME:
        print(
            (
                '[forge registry] duplicate op %s ignored from %s; '
                'already loaded from %s'
            )
            % (
                op_name,
                label,
                OP_PACKAGE_KINDS.get(
                    op_name
                )
                or '?',
            ),
            file=sys.stderr,
        )

        return False

    OPS_BY_NAME[
        op_name
    ] = mod

    OP_SPECS[
        op_name
    ] = spec

    OP_MODULES.append(
        mod
    )

    OP_PACKAGE_KINDS[
        op_name
    ] = root_kind

    OP_PACKAGE_MODULES[
        op_name
    ] = (
        package_module
        or ''
    )

    OP_PACKAGE_PATHS[
        op_name
    ] = _physical_package_path(
        package_module,
        fallback=package_dir,
    )

    return True


def discover_ops():
    OPS_BY_NAME.clear()
    OP_SPECS.clear()
    OP_MODULES[:] = []
    OP_PACKAGE_PATHS.clear()
    OP_PACKAGE_KINDS.clear()
    OP_PACKAGE_MODULES.clear()

    try:
        importlib.invalidate_caches()
    except Exception:
        pass

    for (
        root_kind,
        root_module,
        root,
    ) in _ops_roots():
        resource_names = (
            _resource_package_names(
                root_module
            )
        )

        filesystem_names = (
            _filesystem_package_names(
                root
            )
        )

        names = sorted(
            resource_names
            | filesystem_names
        )

        for name in names:
            package_dir = os.path.join(
                root,
                name,
            )

            path = os.path.join(
                package_dir,
                'op.py',
            )

            mod = None
            err = None
            package_module = (
                root_module
                + '.'
                + name
            )

            if name in resource_names:
                try:
                    (
                        mod,
                        err,
                        package_module,
                    ) = _load_importable_op(
                        root_module,
                        name,
                    )
                except Exception as exc:
                    err = (
                        '%s: %s'
                        % (
                            type(exc).__name__,
                            exc,
                        )
                    )

            if (
                mod is None
                and os.path.isfile(
                    path
                )
            ):
                try:
                    (
                        mod,
                        fallback_err,
                    ) = _load_filesystem_op(
                        path,
                        root_kind,
                        name,
                    )

                    if mod is not None:
                        err = None
                        package_module = ''
                    elif fallback_err:
                        err = fallback_err

                except Exception as exc:
                    err = (
                        '%s: %s'
                        % (
                            type(exc).__name__,
                            exc,
                        )
                    )

            if mod is None:
                if err:
                    print(
                        (
                            '[forge registry] failed to load %s/%s: %s'
                            % (
                                root_kind,
                                name,
                                err,
                            )
                        ),
                        file=sys.stderr,
                    )

                continue

            _register_op(
                mod,
                root_kind,
                name,
                package_module,
                package_dir,
            )


def get_op(name):
    if not OPS_BY_NAME:
        discover_ops()

    return OPS_BY_NAME.get(
        str(
            name
            or ''
        ).upper()
    )


def get_spec(name):
    if not OP_SPECS:
        discover_ops()

    return OP_SPECS.get(
        str(
            name
            or ''
        ).upper()
    )


def get_package_path(name):
    if not OPS_BY_NAME:
        discover_ops()

    return OP_PACKAGE_PATHS.get(
        str(
            name
            or ''
        ).upper()
    )


def get_package_kind(name):
    if not OPS_BY_NAME:
        discover_ops()

    return OP_PACKAGE_KINDS.get(
        str(
            name
            or ''
        ).upper()
    )


def get_package_module(name):
    if not OPS_BY_NAME:
        discover_ops()

    return OP_PACKAGE_MODULES.get(
        str(
            name
            or ''
        ).upper()
    )


def list_ops():
    if not OPS_BY_NAME:
        discover_ops()

    return sorted(
        OPS_BY_NAME.keys()
    )


discover_ops()