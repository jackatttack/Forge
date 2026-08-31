# -*- coding: utf-8 -*-
"""
Portable Forge installer.

Uses only the Python standard library.

The installer places these runtime packages into a Python package directory:

    forge
    forge_core
    forge_packages

Platform adapters, examples, documentation, and bootstrap scripts are not
installed into site-packages.

Examples:

    python install.py --source .

    python install.py --github OWNER/REPOSITORY --ref v0.1.0

    python install.py --source . --target /path/to/site-packages
"""

import argparse
import os
import shutil
import site
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile


RUNTIME_PACKAGES = (
    'forge',
    'forge_core',
    'forge_packages',
)

INSTALL_MARKER = '.portable-forge-installed'
INSTALL_MARKER_TEXT = 'portable-forge-runtime-v1\n'

PYTHONISTA_LAUNCHER_MARKER = 'portable-forge-pythonista-launcher-v1'
PYTHONISTA_LAUNCHER_NAME = 'forge_entry.py'


def absolute(path):
    return os.path.abspath(
        os.path.expanduser(
            str(path)
        )
    )


def is_source_root(path):
    path = absolute(
        path
    )

    for package_name in RUNTIME_PACKAGES:
        package_root = os.path.join(
            path,
            package_name,
        )

        if not os.path.isdir(
            package_root
        ):
            return False

        if not os.path.isfile(
            os.path.join(
                package_root,
                '__init__.py',
            )
        ):
            return False

    return True


def is_pythonista():
    try:
        import editor
        import clipboard
    except Exception:
        return False

    return callable(
        getattr(
            editor,
            'open_file',
            None,
        )
    )


def pythonista_documents_root():
    return absolute(
        '~/Documents'
    )


def pythonista_site_packages():
    return os.path.join(
        pythonista_documents_root(),
        'site-packages-3',
    )


def pythonista_launcher_path():
    return os.path.join(
        pythonista_documents_root(),
        PYTHONISTA_LAUNCHER_NAME,
    )


def pythonista_launcher_source(source_root):
    return os.path.join(
        absolute(
            source_root
        ),
        'adapters',
        'pythonista',
        'Forge.py',
    )


def _read_text(path):
    with open(
        path,
        'r',
        encoding='utf-8',
    ) as handle:
        return handle.read()


def launcher_is_portable(path):
    if not os.path.isfile(
        path
    ):
        return False

    try:
        text = _read_text(
            path
        )
    except Exception:
        return False

    return PYTHONISTA_LAUNCHER_MARKER in text


def pythonista_launcher_preflight(
    source_root,
    force=False,
):
    source = pythonista_launcher_source(
        source_root
    )

    if not os.path.isfile(
        source
    ):
        raise RuntimeError(
            'Pythonista launcher source was not found: '
            + source
        )

    source_text = _read_text(
        source
    )

    if PYTHONISTA_LAUNCHER_MARKER not in source_text:
        raise RuntimeError(
            'Pythonista launcher source is missing the '
            'Portable Forge launcher marker.'
        )

    destination = pythonista_launcher_path()

    if not os.path.exists(
        destination
    ):
        return {
            'source': source,
            'destination': destination,
            'write': True,
            'created': True,
        }

    if not os.path.isfile(
        destination
    ):
        raise RuntimeError(
            (
                'Portable Forge refuses to replace an existing '
                'non-file Pythonista launcher path:\n%s'
            )
            % destination
        )

    destination_text = _read_text(
        destination
    )

    if destination_text == source_text:
        return {
            'source': source,
            'destination': destination,
            'write': False,
            'created': False,
        }

    if not launcher_is_portable(
        destination
    ):
        raise RuntimeError(
            (
                'Portable Forge refuses to overwrite an unrecognised '
                'Pythonista root launcher:\n%s\n'
                'No launcher files were changed.'
            )
            % destination
        )

    if not force:
        raise RuntimeError(
            (
                'A different Portable Forge Pythonista launcher already '
                'exists:\n%s\n'
                'Use --force only when deliberately updating this '
                'marked Portable Forge launcher.'
            )
            % destination
        )

    return {
        'source': source,
        'destination': destination,
        'write': True,
        'created': False,
    }


def install_pythonista_launcher(
    source_root,
    force=False,
):
    plan = pythonista_launcher_preflight(
        source_root,
        force=force,
    )

    source = plan['source']
    destination = plan['destination']

    if not plan['write']:
        return destination

    parent = os.path.dirname(
        destination
    )

    os.makedirs(
        parent,
        exist_ok=True,
    )

    temporary = destination + '.portable-forge-new'

    try:
        shutil.copyfile(
            source,
            temporary,
        )

        os.replace(
            temporary,
            destination,
        )

    finally:
        if os.path.exists(
            temporary
        ):
            os.remove(
                temporary
            )

    return destination


def open_pythonista_launcher(path):
    try:
        import editor

        editor.open_file(
            path
        )

        return True, ''

    except Exception as exc:
        return (
            False,
            '%s: %s'
            % (
                type(exc).__name__,
                exc,
            ),
        )

def default_target():
    if is_pythonista():
        return absolute(
            pythonista_site_packages()
        )

    value = site.getusersitepackages()

    if isinstance(
        value,
        (list, tuple),
    ):
        value = (
            value[0]
            if value
            else ''
        )

    value = str(
        value
        or ''
    ).strip()

    if not value:
        raise RuntimeError(
            'Could not determine user site-packages. '
            'Use --target PATH.'
        )

    return absolute(
        value
    )


def compile_runtime(source_root):
    for package_name in RUNTIME_PACKAGES:
        package_root = os.path.join(
            source_root,
            package_name,
        )

        for dirpath, dirnames, filenames in os.walk(
            package_root
        ):
            dirnames[:] = [
                name
                for name in sorted(
                    dirnames
                )
                if name != '__pycache__'
            ]

            for filename in sorted(
                filenames
            ):
                if not filename.endswith(
                    '.py'
                ):
                    continue

                path = os.path.join(
                    dirpath,
                    filename,
                )

                with open(
                    path,
                    'r',
                    encoding='utf-8',
                ) as handle:
                    source = handle.read()

                compile(
                    source,
                    path,
                    'exec',
                )


def copy_runtime(source_root, destination_root):
    for package_name in RUNTIME_PACKAGES:
        source = os.path.join(
            source_root,
            package_name,
        )

        destination = os.path.join(
            destination_root,
            package_name,
        )

        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                '__pycache__',
                '*.pyc',
                '*.pyo',
            ),
        )


def safe_extract(zip_path, destination):
    destination_real = os.path.realpath(
        destination
    )

    with zipfile.ZipFile(
        zip_path,
        'r',
    ) as archive:
        for info in archive.infolist():
            target = os.path.realpath(
                os.path.join(
                    destination,
                    info.filename,
                )
            )

            if not (
                target == destination_real
                or target.startswith(
                    destination_real
                    + os.sep
                )
            ):
                raise RuntimeError(
                    'Unsafe archive path: '
                    + info.filename
                )

        archive.extractall(
            destination
        )


def find_source_root(search_root):
    search_root = absolute(
        search_root
    )

    if is_source_root(
        search_root
    ):
        return search_root

    for dirpath, dirnames, _filenames in os.walk(
        search_root
    ):
        relative = os.path.relpath(
            dirpath,
            search_root,
        )

        depth = (
            0
            if relative == '.'
            else len(
                relative.split(
                    os.sep
                )
            )
        )

        if depth > 3:
            dirnames[:] = []
            continue

        if is_source_root(
            dirpath
        ):
            return absolute(
                dirpath
            )

    raise RuntimeError(
        'Portable Forge source root not found.'
    )


def github_source(repository, ref, temp_root):
    repository = str(
        repository
        or ''
    ).strip().strip('/')

    if repository.count('/') != 1:
        raise RuntimeError(
            '--github must use OWNER/REPOSITORY.'
        )

    ref = str(
        ref
        or ''
    ).strip()

    if not ref:
        raise RuntimeError(
            '--ref cannot be empty.'
        )

    url = (
        'https://codeload.github.com/'
        + repository
        + '/zip/'
        + urllib.parse.quote(
            ref,
            safe='',
        )
    )

    archive_path = os.path.join(
        temp_root,
        'forge.zip',
    )

    extract_root = os.path.join(
        temp_root,
        'source',
    )

    print(
        'Downloading:',
        url,
    )

    with urllib.request.urlopen(
        url
    ) as response:
        with open(
            archive_path,
            'wb',
        ) as handle:
            while True:
                chunk = response.read(
                    65536
                )

                if not chunk:
                    break

                handle.write(
                    chunk
                )

    os.makedirs(
        extract_root
    )

    safe_extract(
        archive_path,
        extract_root,
    )

    return find_source_root(
        extract_root
    )


def _same_path(left, right):
    try:
        return os.path.realpath(
            absolute(left)
        ) == os.path.realpath(
            absolute(right)
        )
    except Exception:
        return False


def _namespace_candidates(base, package_name):
    return (
        os.path.join(
            base,
            package_name,
        ),
        os.path.join(
            base,
            package_name + '.py',
        ),
    )


def visible_namespace_conflicts(source_root, target):
    source_root = absolute(
        source_root
    )

    target = absolute(
        target
    )

    conflicts = []
    seen = set()

    for raw in list(
        sys.path
    ):
        raw = str(
            raw
            or ''
        ).strip()

        base = absolute(
            raw
            if raw
            else os.getcwd()
        )

        if (
            _same_path(
                base,
                source_root,
            )
            or _same_path(
                base,
                target,
            )
        ):
            continue

        for package_name in RUNTIME_PACKAGES:
            for candidate in _namespace_candidates(
                base,
                package_name,
            ):
                if not os.path.exists(
                    candidate
                ):
                    continue

                key = (
                    package_name,
                    os.path.realpath(
                        candidate
                    ),
                )

                if key in seen:
                    continue

                seen.add(
                    key
                )

                conflicts.append({
                    'package': package_name,
                    'path': candidate,
                })

    return conflicts


def existing_runtime_packages(target):
    target = absolute(
        target
    )

    return [
        package_name
        for package_name in RUNTIME_PACKAGES
        if os.path.exists(
            os.path.join(
                target,
                package_name,
            )
        )
    ]


def package_is_portable_install(path):
    if not os.path.isdir(
        path
    ):
        return False

    marker = os.path.join(
        path,
        INSTALL_MARKER,
    )

    if not os.path.isfile(
        marker
    ):
        return False

    try:
        with open(
            marker,
            'r',
            encoding='utf-8',
        ) as handle:
            value = handle.read()
    except Exception:
        return False

    return value == INSTALL_MARKER_TEXT


def mark_runtime(root):
    for package_name in RUNTIME_PACKAGES:
        package_root = os.path.join(
            root,
            package_name,
        )

        marker = os.path.join(
            package_root,
            INSTALL_MARKER,
        )

        with open(
            marker,
            'w',
            encoding='utf-8',
        ) as handle:
            handle.write(
                INSTALL_MARKER_TEXT
            )


def format_namespace_conflicts(conflicts):
    lines = []

    for item in conflicts:
        lines.append(
            '- %s: %s'
            % (
                item.get('package'),
                item.get('path'),
            )
        )

    return '\n'.join(
        lines
    )

def install(
    source_root,
    target,
    forge_home=None,
    force=False,
):
    source_root = absolute(
        source_root
    )

    target = absolute(
        target
    )

    if forge_home is None:
        forge_home = absolute(
            '~/.forge'
        )
    else:
        forge_home = absolute(
            forge_home
        )

    if not is_source_root(
        source_root
    ):
        raise RuntimeError(
            'Not a Portable Forge source root: '
            + source_root
        )

    compile_runtime(
        source_root
    )

    conflicts = visible_namespace_conflicts(
        source_root,
        target,
    )

    if conflicts:
        raise RuntimeError(
            (
                'Portable Forge namespace collision detected.\n'
                'Installing here could shadow another Forge runtime, '
                'or be shadowed by it.\n'
                '%s\n'
                'No files were changed.\n'
                'Choose an isolated target or deliberately migrate '
                'the conflicting runtime first.'
            )
            % format_namespace_conflicts(
                conflicts
            )
        )

    existing = existing_runtime_packages(
        target
    )

    if existing:
        foreign = []

        for package_name in existing:
            path = os.path.join(
                target,
                package_name,
            )

            if not package_is_portable_install(
                path
            ):
                foreign.append(
                    package_name
                )

        if foreign:
            raise RuntimeError(
                (
                    'Refusing to replace unrecognised existing package(s): %s.\n'
                    '--force only replaces packages carrying the '
                    'Portable Forge installer marker.\n'
                    'No files were changed.'
                )
                % ', '.join(
                    foreign
                )
            )

        if not force:
            raise RuntimeError(
                (
                    'Portable Forge already exists in target: %s.\n'
                    'Use --force only when deliberately replacing '
                    'this marked Portable Forge installation.'
                )
                % ', '.join(
                    existing
                )
            )

    os.makedirs(
        target,
        exist_ok=True,
    )

    os.makedirs(
        forge_home,
        exist_ok=True,
    )

    stage = tempfile.mkdtemp(
        prefix='.forge-install-',
        dir=target,
    )

    try:
        copy_runtime(
            source_root,
            stage,
        )

        mark_runtime(
            stage
        )

        compile_runtime(
            stage
        )

        if existing:
            for package_name in existing:
                path = os.path.join(
                    target,
                    package_name,
                )

                if os.path.isdir(
                    path
                ):
                    shutil.rmtree(
                        path
                    )
                else:
                    os.remove(
                        path
                    )

        for package_name in RUNTIME_PACKAGES:
            shutil.move(
                os.path.join(
                    stage,
                    package_name,
                ),
                os.path.join(
                    target,
                    package_name,
                ),
            )

    finally:
        shutil.rmtree(
            stage,
            ignore_errors=True,
        )

    return {
        'target': target,
        'forge_home': forge_home,
    }


def parser():
    result = argparse.ArgumentParser(
        description='Install Portable Forge without pip.'
    )

    source = result.add_mutually_exclusive_group()

    source.add_argument(
        '--source',
        help='Local Portable Forge repository.',
    )

    source.add_argument(
        '--github',
        help='GitHub repository as OWNER/REPOSITORY.',
    )

    result.add_argument(
        '--ref',
        default='main',
        help='Git ref used with --github.',
    )

    result.add_argument(
        '--target',
        help='Python package directory.',
    )

    result.add_argument(
        '--home',
        help='Writable Forge home. Default: ~/.forge.',
    )

    result.add_argument(
        '--force',
        action='store_true',
        help=(
            'Replace an existing installation only when its packages '
            'are marked as Portable Forge.'
        ),
    )

    return result


def main(argv=None):
    args = parser().parse_args(
        argv
    )

    target = absolute(
        args.target
        or default_target()
    )

    forge_home = absolute(
        args.home
        or '~/.forge'
    )

    temp_root = None

    try:
        if args.source:
            source_root = find_source_root(
                args.source
            )

        elif args.github:
            temp_root = tempfile.mkdtemp(
                prefix='portable-forge-download-'
            )

            source_root = github_source(
                args.github,
                args.ref,
                temp_root,
            )

        else:
            source_root = find_source_root(
                os.path.dirname(
                    os.path.abspath(
                        __file__
                    )
                )
            )

        pythonista = is_pythonista()
        launcher_plan = None

        if pythonista:
            launcher_plan = pythonista_launcher_preflight(
                source_root,
                force=args.force,
            )

        installed = install(
            source_root,
            target,
            forge_home=forge_home,
            force=args.force,
        )

        launcher = None
        launcher_opened = False
        launcher_open_error = ''
        launcher_should_open = False

        if pythonista:
            launcher = install_pythonista_launcher(
                source_root,
                force=args.force,
            )

            launcher_should_open = bool(
                launcher_plan
                and launcher_plan.get('created')
            )

            if launcher_should_open:
                (
                    launcher_opened,
                    launcher_open_error,
                ) = open_pythonista_launcher(
                    launcher
                )

        print('')
        print(
            'Portable Forge installed.'
        )

        print(
            'site-packages:',
            installed['target'],
        )

        print(
            'Forge home:',
            installed['forge_home'],
        )

        if launcher:
            print(
                'Pythonista launcher:',
                launcher,
            )

            if launcher_opened:
                print(
                    'Pythonista launcher opened in the editor.'
                )
            elif launcher_should_open:
                print(
                    'Pythonista launcher created but could not be '
                    'opened automatically: '
                    + launcher_open_error
                )
            else:
                print(
                    'Pythonista launcher ready. Existing or updated '
                    'launchers are not auto-opened.'
                )

        print('')

        if launcher:
            print(
                'Next: put a Forge bundle on the clipboard and run '
                + PYTHONISTA_LAUNCHER_NAME
            )
        else:
            print(
                'Next: import forge'
            )

        return 0

    finally:
        if temp_root:
            shutil.rmtree(
                temp_root,
                ignore_errors=True,
            )


if __name__ == '__main__':
    raise SystemExit(
        main()
    )