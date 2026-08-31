# -*- coding: utf-8 -*-
"""
Package-shaped op registry for Forge.

Discovers ops from:

    forge_packages/core_ops/<name>/op.py
    forge_packages/custom_ops/<name>/op.py

Both roots are first-class op package locations.

core_ops is the public/daily-driver base vocabulary.
custom_ops is Jack-local extension space.

A valid package in either folder is auto-discovered as a Forge op.
"""

import importlib.util
import os
import sys


OPS_BY_NAME = {}
OP_SPECS = {}
OP_MODULES = []
OP_PACKAGE_PATHS = {}
OP_PACKAGE_KINDS = {}


def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ops_roots():
    base = os.path.join(_root_dir(), 'forge_packages')
    return [
        ('core_ops', os.path.join(base, 'core_ops')),
        ('custom_ops', os.path.join(base, 'custom_ops')),
    ]


def _safe_module_part(value):
    text = str(value or '').strip().lower()
    out = []
    for ch in text:
        if ch.isalnum() or ch == '_':
            out.append(ch)
        else:
            out.append('_')
    return ''.join(out) or 'op'


def _load_op_module(path, root_kind, package_name):
    mod_name = 'forge_op_%s_%s' % (
        _safe_module_part(root_kind),
        _safe_module_part(package_name),
    )
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None, 'could not create import spec'
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod, None


def discover_ops():
    OPS_BY_NAME.clear()
    OP_SPECS.clear()
    OP_MODULES[:] = []
    OP_PACKAGE_PATHS.clear()
    OP_PACKAGE_KINDS.clear()

    for root_kind, root in _ops_roots():
        if not os.path.isdir(root):
            continue

        for name in sorted(os.listdir(root)):
            package_dir = os.path.join(root, name)
            path = os.path.join(package_dir, 'op.py')
            if not os.path.isfile(path):
                continue

            label = '%s/%s' % (root_kind, name)

            try:
                mod, err = _load_op_module(path, root_kind, name)
            except Exception as e:
                print('[forge registry] failed to load %s: %s' % (label, e), file=sys.stderr)
                continue

            if err or mod is None:
                print('[forge registry] failed to load %s: %s' % (label, err), file=sys.stderr)
                continue

            spec = getattr(mod, 'SPEC', None)
            if not isinstance(spec, dict) or not spec.get('name'):
                print('[forge registry] %s has no valid SPEC' % label, file=sys.stderr)
                continue

            op_name = str(spec.get('name')).upper()

            if op_name in OPS_BY_NAME:
                print(
                    '[forge registry] duplicate op %s ignored from %s; already loaded from %s' % (
                        op_name,
                        label,
                        OP_PACKAGE_KINDS.get(op_name) or '?',
                    ),
                    file=sys.stderr,
                )
                continue

            OPS_BY_NAME[op_name] = mod
            OP_SPECS[op_name] = spec
            OP_MODULES.append(mod)
            OP_PACKAGE_PATHS[op_name] = package_dir
            OP_PACKAGE_KINDS[op_name] = root_kind


def get_op(name):
    if not OPS_BY_NAME:
        discover_ops()
    return OPS_BY_NAME.get(str(name or '').upper())


def get_spec(name):
    if not OP_SPECS:
        discover_ops()
    return OP_SPECS.get(str(name or '').upper())


def get_package_path(name):
    if not OP_PACKAGE_PATHS:
        discover_ops()
    return OP_PACKAGE_PATHS.get(str(name or '').upper())


def get_package_kind(name):
    if not OP_PACKAGE_KINDS:
        discover_ops()
    return OP_PACKAGE_KINDS.get(str(name or '').upper())


def list_ops():
    if not OPS_BY_NAME:
        discover_ops()
    return sorted(OPS_BY_NAME.keys())


discover_ops()