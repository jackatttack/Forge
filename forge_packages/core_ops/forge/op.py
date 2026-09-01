# -*- coding: utf-8 -*-
"""
FORGE meta op.

One read-only home for Forge's own machinery:

- language discovery
- installed operation discovery
- help
- package audit
- environment/config inspection
- stored run inspection
"""

import importlib
import importlib.util
import os

try:
    from importlib import resources as importlib_resources
except ImportError:
    importlib_resources = None

from forge_core.language import (
    classify_op,
    public_ops,
)
from forge_core.registry import (
    OPS_BY_NAME,
    discover_ops,
    get_package_kind,
    get_package_module,
    get_package_path,
)
from forge_core.run_storage import (
    list_runs,
    read_text,
    runs_root,
)


SPEC = {
    'name': 'FORGE',
    'target_kind': 'none',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'ARGS',
        'LIMIT',
        'MODE',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Inspect Forge itself: public language, help, health, configuration, and stored runs.',
    'minimal_example': [
        'FORGE',
        '',
        'FORGE ops',
        '',
        'FORGE help WRITE',
        '',
        'FORGE audit',
        '',
        'FORGE runs latest',
    ],
}


HINTS = {
    '_max_hints': 1,

    'unknown forge command': {
        'message': 'Unknown FORGE subcommand.',
        'why': 'FORGE only handles Forge machinery and self-inspection.',
        'example': [
            'FORGE ops',
            'FORGE help WRITE',
            'FORGE audit',
            'FORGE config',
            'FORGE runs',
        ],
    },
}


def validate(parsed_op):
    return []


def _as_int(
    value,
    default,
):
    try:
        return max(
            1,
            int(
                str(value).strip()
            ),
        )
    except Exception:
        return default


def _raw_args(parsed_op):
    directives = (
        parsed_op.get(
            'directives'
        )
        or {}
    )

    return (
        directives.get(
            'ARGS'
        )
        or parsed_op.get(
            'target'
        )
        or ''
    ).strip()


def _usage():
    return '\n'.join([
        'FORGE',
        '',
        'Public language:',
        '  FORGE ops',
        '',
        'Installed powers:',
        '  FORGE ops all',
        '',
        'Help:',
        '  FORGE help <OP>',
        '  FORGE help <OP> full',
        '  FORGE help <OP> contract',
        '',
        'Health:',
        '  FORGE audit',
        '',
        'Context:',
        '  FORGE config',
        '',
        'Run history:',
        '  FORGE runs',
        '  FORGE runs latest',
        '  FORGE runs show <stamp> [packet|surface|bundle|json]',
    ])


def _ops(result, all_ops=False):
    discover_ops()

    installed = sorted(
        OPS_BY_NAME.keys()
    )

    if all_ops:
        names = installed
        title = 'FORGE OPS — ALL INSTALLED'
    else:
        names = [
            name
            for name in public_ops()
            if name in OPS_BY_NAME
        ]
        title = 'FORGE OPS — PUBLIC'

    lines = [
        title,
        '',
    ]

    rows = []

    for name in names:
        mod = OPS_BY_NAME.get(
            name
        )

        help_data = getattr(
            mod,
            'HELP',
            {},
        ) or {}

        summary = (
            help_data.get(
                'summary'
            )
            or '(no summary)'
        )

        kind = classify_op(
            name
        )

        rows.append({
            'name': name,
            'kind': kind,
            'summary': summary,
        })

        if all_ops:
            lines.append(
                '- %-12s %-9s %s'
                % (
                    name,
                    kind,
                    summary,
                )
            )
        else:
            lines.append(
                '- %-12s %s'
                % (
                    name,
                    summary,
                )
            )

    lines.extend([
        '',
        'Need syntax or examples?',
        '  FORGE help <OP>',
        '',
        'Need deeper behaviour?',
        '  FORGE help <OP> full',
    ])

    result['status'] = 'APPLIED'
    result['message'] = (
        '%d %s op(s)'
        % (
            len(rows),
            (
                'installed'
                if all_ops
                else 'public'
            ),
        )
    )
    result['preview'] = '\n'.join(
        lines
    ).rstrip()
    result['data'] = {
        'mode': (
            'all'
            if all_ops
            else 'public'
        ),
        'ops': rows,
    }

def _package_leaf(
    name,
    folder='',
):
    package_name = (
        get_package_module(
            name
        )
        or ''
    )

    if package_name:
        return package_name.rsplit(
            '.',
            1,
        )[-1]

    return os.path.basename(
        folder
        or ''
    )


def _package_resource_bytes(
    name,
    folder,
    resource_name,
):
    package_name = (
        get_package_module(
            name
        )
        or ''
    )

    if (
        package_name
        and importlib_resources is not None
    ):
        try:
            package = importlib.import_module(
                package_name
            )

            files_fn = getattr(
                importlib_resources,
                'files',
                None,
            )

            if callable(
                files_fn
            ):
                item = files_fn(
                    package
                ).joinpath(
                    resource_name
                )

                if item.is_file():
                    return item.read_bytes()

            elif importlib_resources.is_resource(
                package,
                resource_name,
            ):
                return importlib_resources.read_binary(
                    package,
                    resource_name,
                )

        except Exception:
            pass

    if folder:
        path = os.path.join(
            folder,
            resource_name,
        )

        if os.path.isfile(
            path
        ):
            try:
                with open(
                    path,
                    'rb',
                ) as handle:
                    return handle.read()
            except Exception:
                pass

    return None


def _package_resource_exists(
    name,
    folder,
    resource_name,
):
    return (
        _package_resource_bytes(
            name,
            folder,
            resource_name,
        )
        is not None
    )


def _read_package_text(
    name,
    folder,
    resource_name,
):
    raw = _package_resource_bytes(
        name,
        folder,
        resource_name,
    )

    if raw is None:
        return ''

    try:
        return raw.decode(
            'utf-8',
            'replace',
        )
    except Exception:
        return str(
            raw
        )


def _load_manifest(
    folder,
    op_name,
):
    package_name = (
        get_package_module(
            op_name
        )
        or ''
    )

    if package_name:
        module_name = (
            package_name
            + '.manifest'
        )

        try:
            mod = importlib.import_module(
                module_name
            )

            manifest = getattr(
                mod,
                'MANIFEST',
                None,
            )

            if not isinstance(
                manifest,
                dict,
            ):
                return None, (
                    'MANIFEST is not a dict'
                )

            return manifest, None

        except Exception as e:
            if not folder:
                return None, (
                    'manifest import failed: %s: %s'
                    % (
                        type(e).__name__,
                        e,
                    )
                )

    path = os.path.join(
        folder,
        'manifest.py',
    )

    if not os.path.isfile(
        path
    ):
        return None, (
            'missing manifest.py'
        )

    try:
        mod_name = (
            'forge_next_manifest_'
            + str(
                op_name
            ).lower()
        )

        spec = (
            importlib.util.spec_from_file_location(
                mod_name,
                path,
            )
        )

        if (
            spec is None
            or spec.loader is None
        ):
            return None, (
                'could not create manifest import spec'
            )

        mod = (
            importlib.util.module_from_spec(
                spec
            )
        )

        spec.loader.exec_module(
            mod
        )

        manifest = getattr(
            mod,
            'MANIFEST',
            None,
        )

        if not isinstance(
            manifest,
            dict,
        ):
            return None, (
                'MANIFEST is not a dict'
            )

        return manifest, None

    except Exception as e:
        return None, (
            'manifest import failed: %s: %s'
            % (
                type(e).__name__,
                e,
            )
        )


def _contract_issues(
    name,
    mod,
):
    issues = []

    folder = get_package_path(
        name
    ) or ''

    package_name = (
        get_package_module(
            name
        )
        or ''
    )

    if (
        not folder
        and not package_name
    ):
        issues.append(
            'package metadata unavailable'
        )
        return issues, None

    if not _package_resource_exists(
        name,
        folder,
        'README.txt',
    ):
        issues.append(
            'missing README.txt'
        )

    manifest, manifest_error = (
        _load_manifest(
            folder,
            name,
        )
    )

    if manifest_error:
        issues.append(
            manifest_error
        )
    else:
        for key in (
            'name',
            'op',
            'kind',
            'version',
            'summary',
        ):
            if key not in manifest:
                issues.append(
                    'MANIFEST missing '
                    + key
                )

        if manifest.get(
            'name'
        ) != _package_leaf(
            name,
            folder,
        ):
            issues.append(
                'MANIFEST name mismatch'
            )

        if str(
            manifest.get(
                'op'
            )
            or ''
        ).upper() != name:
            issues.append(
                'MANIFEST op mismatch'
            )

        expected_kind = {
            'core_ops': 'core-op',
            'custom_ops': 'custom-op',
        }.get(
            get_package_kind(
                name
            ),
            '',
        )

        if (
            expected_kind
            and manifest.get(
                'kind'
            ) != expected_kind
        ):
            issues.append(
                'MANIFEST kind should be '
                + expected_kind
            )

    spec = getattr(
        mod,
        'SPEC',
        None,
    )

    if not isinstance(
        spec,
        dict,
    ):
        issues.append(
            'missing SPEC dict'
        )
    else:
        for key in (
            'name',
            'target_kind',
            'body_mode',
            'allowed_directives',
            'required_directives',
        ):
            if key not in spec:
                issues.append(
                    'SPEC missing '
                    + key
                )

        if str(
            spec.get(
                'name'
            )
            or ''
        ).upper() != name:
            issues.append(
                'SPEC name mismatch'
            )

    help_data = getattr(
        mod,
        'HELP',
        None,
    )

    if not isinstance(
        help_data,
        dict,
    ):
        issues.append(
            'missing HELP dict'
        )
    elif not help_data.get(
        'summary'
    ):
        issues.append(
            'HELP missing summary'
        )

    if not callable(
        getattr(
            mod,
            'validate',
            None,
        )
    ):
        issues.append(
            'missing validate()'
        )

    if not callable(
        getattr(
            mod,
            'execute',
            None,
        )
    ):
        issues.append(
            'missing execute()'
        )

    return issues, manifest


def _help(
    result,
    name,
    mode='quick',
):
    discover_ops()

    name = str(
        name
        or ''
    ).strip().upper()

    mod = OPS_BY_NAME.get(
        name
    )

    if mod is None:
        result['status'] = (
            'FAILED_NOT_FOUND'
        )
        result['message'] = (
            'Unknown op: '
            + name
        )
        return

    folder = (
        get_package_path(
            name
        )
        or ''
    )

    spec = getattr(
        mod,
        'SPEC',
        {},
    ) or {}

    help_data = getattr(
        mod,
        'HELP',
        {},
    ) or {}

    issues, manifest = (
        _contract_issues(
            name,
            mod,
        )
    )

    lines = [
        'FORGE HELP ' + name,
        '',
        help_data.get(
            'summary'
        )
        or '(no summary)',
    ]

    if mode == 'contract':
        lines.extend([
            '',
            'CONTRACT',
            (
                'PASS package contract ok'
                if not issues
                else 'FAIL '
                + '; '.join(
                    issues
                )
            ),
        ])

    elif mode == 'full':
        readme = _read_package_text(
            name,
            folder,
            'README.txt',
        ).rstrip()

        if readme:
            lines.extend([
                '',
                readme,
            ])

        lines.extend([
            '',
            'SPEC',
            'target: '
            + str(
                spec.get(
                    'target_kind'
                )
                or '-'
            ),
            'body: '
            + str(
                spec.get(
                    'body_mode'
                )
                or '-'
            ),
            'directives: '
            + (
                ', '.join(
                    sorted(
                        spec.get(
                            'allowed_directives'
                        )
                        or []
                    )
                )
                or '-'
            ),
        ])

    else:
        examples = help_data.get(
            'minimal_example'
        ) or []

        if examples:
            lines.extend([
                '',
                'EXAMPLE',
            ])
            lines.extend(
                str(x)
                for x in examples
            )

        directives = sorted(
            spec.get(
                'allowed_directives'
            )
            or []
        )

        lines.extend([
            '',
            'DIRECTIVES',
            (
                ', '.join(
                    directives
                )
                if directives
                else '-'
            ),
        ])

    result['status'] = 'APPLIED'
    result['message'] = (
        'Help for '
        + name
    )
    result['preview'] = '\n'.join(
        lines
    ).rstrip()
    result['data'] = {
        'op': name,
        'mode': mode,
        'manifest': manifest or {},
        'contract_issues': issues,
    }


def _audit(result):
    discover_ops()

    lines = [
        'FORGE AUDIT',
        '',
    ]

    total = 0
    failed = 0

    for name in sorted(
        OPS_BY_NAME.keys()
    ):
        total += 1

        mod = OPS_BY_NAME.get(
            name
        )

        issues, _manifest = (
            _contract_issues(
                name,
                mod,
            )
        )

        if issues:
            failed += 1
            lines.append(
                '- FAIL %-12s %s'
                % (
                    name,
                    '; '.join(
                        issues
                    ),
                )
            )
        else:
            lines.append(
                '- PASS %-12s package contract ok'
                % name
            )

    lines.extend([
        '',
        'total: %d' % total,
        'failed: %d' % failed,
    ])

    result['status'] = (
        'FAILED_VALIDATE'
        if failed
        else 'APPLIED'
    )

    result['message'] = (
        (
            '%d audit failure(s)'
            % failed
        )
        if failed
        else 'audit clean'
    )

    result['preview'] = '\n'.join(
        lines
    )

    result['data'] = {
        'total': total,
        'failed': failed,
    }


def _config(ctx, result):
    environment = (
        (ctx or {}).get(
            'environment'
        )
        or {}
    )

    features = dict(
        environment.get(
            'features'
        )
        or {}
    )

    capabilities = dict(
        environment.get(
            'capabilities'
        )
        or {}
    )

    storage = dict(
        environment.get(
            'storage'
        )
        or {}
    )

    lines = [
        'FORGE CONFIG',
        '',
        'host: '
        + str(
            environment.get(
                'host'
            )
            or ''
        ),
        'project_root: '
        + str(
            environment.get(
                'project_root'
            )
            or ''
        ),
        'forge_home: '
        + str(
            environment.get(
                'forge_home'
            )
            or ''
        ),
        'storage_root: '
        + str(
            environment.get(
                'storage_root'
            )
            or ''
        ),
        'aliases_path: '
        + str(
            environment.get(
                'aliases_path'
            )
            or ''
        ),
        'config_path: '
        + str(
            environment.get(
                'config_path'
            )
            or ''
        ),
        '',
        'storage:',
    ]

    if storage:
        for key in sorted(
            storage
        ):
            lines.append(
                '  %s: %s'
                % (
                    key,
                    storage.get(
                        key
                    ),
                )
            )
    else:
        lines.append(
            '  (none)'
        )

    lines.append('')
    lines.append(
        'features:'
    )

    if features:
        for key in sorted(
            features
        ):
            lines.append(
                '  %s: %s'
                % (
                    key,
                    features.get(
                        key
                    ),
                )
            )
    else:
        lines.append(
            '  (none)'
        )

    lines.append('')
    lines.append(
        'capabilities:'
    )

    if capabilities:
        for key in sorted(
            capabilities
        ):
            lines.append(
                '  %s: %s'
                % (
                    key,
                    capabilities.get(
                        key
                    ),
                )
            )
    else:
        lines.append(
            '  (none)'
        )

    result['status'] = 'APPLIED'
    result['message'] = (
        'Resolved Forge context'
    )
    result['preview'] = '\n'.join(
        lines
    )
    result['data'] = {
        'environment': dict(
            environment
        ),
    }


def _runs(
    ctx,
    parsed_op,
    result,
    args,
):
    from forge_core.environment import path_from_ctx

    environment = (
        (ctx or {}).get(
            'environment'
        )
        or {}
    )

    project_root = path_from_ctx(
        ctx,
        'project_root',
    )

    directives = (
        parsed_op.get(
            'directives'
        )
        or {}
    )

    limit = _as_int(
        directives.get(
            'LIMIT'
        ),
        10,
    )

    run_mode = str(
        (
            (
                (ctx or {}).get(
                    'run'
                )
                or {}
            ).get(
                'mode'
            )
            or 'dev'
        )
    )

    names = list_runs(
        project_root,
        limit=limit,
        mode=run_mode,
        environment=environment,
    )

    args = str(
        args
        or ''
    ).strip()

    if not args or args == 'list':
        lines = [
            'FORGE RUNS',
            'root: '
            + runs_root(
                project_root,
                mode=run_mode,
                environment=environment,
            ),
        ]

        if names:
            lines.extend(
                '- ' + stamp
                for stamp in names
            )
        else:
            lines.append(
                '(none)'
            )

        result['status'] = 'APPLIED'
        result['message'] = (
            '%d stored run(s)'
            % len(names)
        )
        result['preview'] = '\n'.join(
            lines
        )
        result['data'] = {
            'runs': names,
        }
        return

    parts = args.split()

    if parts[0] == 'latest':
        if not names:
            result['status'] = (
                'FAILED_NOT_FOUND'
            )
            result['message'] = (
                'No stored runs'
            )
            return

        stamp = names[0]

        packet = (
            read_text(
                project_root,
                stamp,
                'packet.txt',
                mode=run_mode,
                environment=environment,
            )
            or ''
        )

        surface = (
            read_text(
                project_root,
                stamp,
                'surface.txt',
                mode=run_mode,
                environment=environment,
            )
            or ''
        )

        lines = [
            'FORGE RUNS latest '
            + stamp,
            '',
            'PACKET',
            packet.rstrip(),
        ]

        if surface.strip():
            lines.extend([
                '',
                'SURFACE',
                surface.rstrip(),
            ])

        result['status'] = 'APPLIED'
        result['message'] = (
            'Latest run: '
            + stamp
        )
        result['preview'] = '\n'.join(
            lines
        ).rstrip()
        result['data'] = {
            'stamp': stamp,
        }
        return

    if parts[0] == 'show':
        if len(parts) < 2:
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                'FORGE runs show requires a stamp'
            )
            return

        stamp = parts[1]

        kind = (
            parts[2]
            if len(parts) > 2
            else 'packet'
        )

        file_map = {
            'packet': 'packet.txt',
            'surface': 'surface.txt',
            'bundle': 'bundle.txt',
            'json': 'run.json',
            'run': 'run.json',
        }

        filename = file_map.get(
            kind
        )

        if not filename:
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                'Unknown FORGE runs show kind: '
                + kind
            )
            return

        text = read_text(
            project_root,
            stamp,
            filename,
            mode=run_mode,
            environment=environment,
        )

        if text is None:
            result['status'] = (
                'FAILED_NOT_FOUND'
            )
            result['message'] = (
                'Run artifact not found: %s %s'
                % (
                    stamp,
                    filename,
                )
            )
            return

        result['status'] = 'APPLIED'
        result['message'] = (
            'Run %s %s'
            % (
                stamp,
                kind,
            )
        )
        result['preview'] = (
            text.rstrip()
        )
        result['data'] = {
            'stamp': stamp,
            'kind': kind,
        }
        return

    result['status'] = (
        'FAILED_PARSE'
    )
    result['message'] = (
        'Unknown FORGE runs args: '
        + args
    )


def execute(ctx, parsed_op, result):
    raw = _raw_args(
        parsed_op
    )

    if not raw:
        result['status'] = 'APPLIED'
        result['message'] = (
            'Forge'
        )
        result['preview'] = (
            _usage()
        )
        result['data'] = {
            'mode': 'home',
        }
        return

    parts = raw.split()
    command = parts[0].lower()
    rest = ' '.join(
        parts[1:]
    ).strip()

    if command == 'ops':
        _ops(
            result,
            all_ops=(
                rest.lower() == 'all'
            ),
        )
        return

    if command == 'help':
        help_parts = rest.split()

        if not help_parts:
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                'FORGE help requires an op name'
            )
            return

        name = help_parts[0]

        mode = (
            help_parts[1].lower()
            if len(help_parts) > 1
            else 'quick'
        )

        if mode not in (
            'quick',
            'full',
            'contract',
        ):
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                'FORGE help mode must be quick, full, or contract'
            )
            return

        _help(
            result,
            name,
            mode=mode,
        )
        return

    if command == 'audit':
        _audit(
            result
        )
        return

    if command == 'config':
        _config(
            ctx,
            result,
        )
        return

    if command == 'runs':
        _runs(
            ctx,
            parsed_op,
            result,
            rest,
        )
        return

    result['status'] = (
        'FAILED_PARSE'
    )
    result['message'] = (
        'Unknown FORGE command: '
        + command
    )