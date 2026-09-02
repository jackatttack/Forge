# -*- coding: utf-8 -*-
"""
Standard host for portable Forge.

This is the ordinary Python edge around the portable core.

Host responsibilities:
- choose project_root when the caller does not
- choose writable Forge home
- load user configuration
- construct resolved environment
- read bundle input for CLI use
- print standard presentation

Portable core remains responsible for parsing, execution, storage semantics,
recovery data, and canonical packet generation.
"""

import argparse
import os
import sys

from forge.core.config import (
    load_config,
    resolve_config,
)
from forge.core.environment import (
    make_environment,
)
from forge.core.presentation.standard import (
    render_standard,
)
from forge.core.runner import (
    run_text as core_run_text,
)


HERE = os.path.dirname(
    os.path.abspath(__file__)
)

FIRST_BOOT_PATH = os.path.join(
    HERE,
    'FIRST_BOOT.txt',
)


def _absolute(path):
    return os.path.abspath(
        os.path.expanduser(
            str(path)
        )
    )


def default_forge_home():
    """
    Return the standard host's writable Forge home.

    Installed source code is not used as writable state.
    """
    configured = str(
        os.environ.get(
            'FORGE_HOME'
        )
        or ''
    ).strip()

    if configured:
        return _absolute(
            configured
        )

    return _absolute(
        '~/.forge'
    )


def standard_environment(
    project_root=None,
    forge_home=None,
    capabilities=None,
    config_path=None,
):
    """Resolve ordinary Python host facts into one Forge environment."""
    root = _absolute(
        project_root
        or os.getcwd()
    )

    home = _absolute(
        forge_home
        or default_forge_home()
    )

    os.makedirs(
        home,
        exist_ok=True,
    )

    config = load_config(
        home,
        path=config_path,
    )

    resolved = resolve_config(
        config,
        home,
        path=config_path,
    )

    return make_environment(
        project_root=root,
        forge_home=home,
        storage_root=resolved[
            'storage_root'
        ],
        aliases_path=resolved[
            'aliases_path'
        ],
        capabilities=(
            capabilities
            or {}
        ),
        host='standard',
        storage=resolved[
            'storage'
        ],
        features=resolved[
            'features'
        ],
        config_path=resolved[
            'config_path'
        ],
    )


def run_text(
    bundle_text,
    project_root=None,
    mode='dev',
    store=True,
    environment=None,
    forge_home=None,
    capabilities=None,
    config_path=None,
    on_event=None,
):
    """
    Execute Forge from normal Python code.

    Supplying environment gives the caller complete control.

    Otherwise the standard host resolves project_root and writable Forge home.

    ``on_event`` optionally receives structured execution progress from the
    portable core. Presentation remains the host's responsibility.
    """
    if environment is None:
        environment = standard_environment(
            project_root=project_root,
            forge_home=forge_home,
            capabilities=capabilities,
            config_path=config_path,
        )

    return core_run_text(
        bundle_text,
        project_root=environment.get(
            'project_root'
        ),
        mode=mode,
        store=store,
        environment=environment,
        on_event=on_event,
    )


def first_boot_text():
    """Return the portable Forge first-boot prompt."""
    with open(
        FIRST_BOOT_PATH,
        'r',
        encoding='utf-8',
    ) as handle:
        return handle.read()


def _parser():
    parser = argparse.ArgumentParser(
        prog='python -m forge',
        description=(
            'Run a Forge bundle using the standard pure-Python host.'
        ),
    )

    parser.add_argument(
        'bundle_file',
        nargs='?',
        help='Bundle text file. If omitted, read stdin.',
    )

    parser.add_argument(
        '--project',
        help='Project root. Defaults to current working directory.',
    )

    parser.add_argument(
        '--home',
        help='Writable Forge home. Defaults to FORGE_HOME or ~/.forge.',
    )

    parser.add_argument(
        '--config',
        help='Optional forge.json path.',
    )

    parser.add_argument(
        '--mode',
        default='dev',
        help='Run storage lane. Default: dev.',
    )

    parser.add_argument(
        '--no-store',
        action='store_true',
        help='Do not persist this run.',
    )

    parser.add_argument(
        '--first-boot',
        action='store_true',
        help='Print the portable AI first-boot prompt.',
    )

    return parser


def _read_bundle(args, stdin):
    if args.bundle_file:
        with open(
            args.bundle_file,
            'r',
            encoding='utf-8',
        ) as handle:
            return handle.read()

    if (
        hasattr(
            stdin,
            'isatty',
        )
        and stdin.isatty()
    ):
        return None

    return stdin.read()


def main(
    argv=None,
    stdin=None,
    stdout=None,
):
    """Standard CLI entrypoint."""
    argv = list(
        sys.argv[1:]
        if argv is None
        else argv
    )

    stdin = (
        sys.stdin
        if stdin is None
        else stdin
    )

    stdout = (
        sys.stdout
        if stdout is None
        else stdout
    )

    parser = _parser()
    args = parser.parse_args(
        argv
    )

    if args.first_boot:
        text = first_boot_text()

        stdout.write(
            text
        )

        if (
            text
            and not text.endswith('\n')
        ):
            stdout.write('\n')

        return 0

    bundle = _read_bundle(
        args,
        stdin,
    )

    if bundle is None:
        parser.print_help(
            file=stdout
        )
        return 2

    if not str(bundle).strip():
        stdout.write(
            'Forge: no bundle text supplied.\n'
        )
        return 2

    run = run_text(
        bundle,
        project_root=args.project,
        forge_home=args.home,
        mode=args.mode,
        store=not args.no_store,
        config_path=args.config,
    )

    stdout.write(
        render_standard(
            run
        )
    )

    if (
        str(
            run.get('status')
            or ''
        ).upper()
        == 'APPLIED'
    ):
        return 0

    return 1