# -*- coding: utf-8 -*-
"""
Portable Forge installer.

Uses only the Python standard library.

The installer places one Forge package into a Python package directory:

    forge

Portable core, bundled operations, and supported host adapters live beneath
the forge namespace.

Examples, documentation, bootstrap scripts, and host launchers are not part
of the portable runtime unless a host-specific installation explicitly adds
them.

Examples:

    python install.py --source .

    python install.py --github OWNER/REPOSITORY --ref v0.1.1

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
)

# Portable Forge versions before the single-namespace layout installed these
# as separate top-level packages. They are recognised only so an owned legacy
# installation can be migrated safely.
LEGACY_RUNTIME_PACKAGES = (
    'forge_core',
    'forge_packages',
)

INSTALL_MARKER = '.portable-forge-installed'
INSTALL_MARKER_TEXT = 'portable-forge-runtime-v1\n'

PYTHONISTA_LAUNCHER_MARKER = 'portable-forge-pythonista-launcher-v1'
PYTHONISTA_LAUNCHER_NAME = 'forge_entry.py'

# Legacy root renderer ownership data. New installations use the packaged
# forge.adapters.pythonista console UI instead.
PYTHONISTA_RENDERER_MARKER = 'portable-forge-pythonista-live-ui-v1'
PYTHONISTA_RENDERER_NAME = 'forge_console_ui.py'

PYTHONIDE_LAUNCHER_MARKER = 'portable-forge-pythonide-launcher-v1'
PYTHONIDE_LAUNCHER_NAME = 'forge-entry.py'

PYTHONIDE_LIVE_UI_MARKER = 'portable-forge-pythonide-live-ui-v1'
PYTHONIDE_LIVE_UI_NAME = 'forge_live_ui.py'

PYTHONIDE_ADAPTER_FILES = (
    (
        PYTHONIDE_LAUNCHER_NAME,
        PYTHONIDE_LAUNCHER_MARKER,
    ),
    (
        PYTHONIDE_LIVE_UI_NAME,
        PYTHONIDE_LIVE_UI_MARKER,
    ),
)

JUNO_LAUNCHER_MARKER = 'portable-forge-juno-launcher-v1'
JUNO_LAUNCHER_NAME = 'forge_entry.py'

JUNO_CLIPBOARD_MARKER = 'portable-forge-juno-clipboard-v1'
JUNO_CLIPBOARD_NAME = 'juno_clipboard.py'

JUNO_ADAPTER_FILES = (
    (
        JUNO_LAUNCHER_NAME,
        JUNO_LAUNCHER_MARKER,
    ),
    (
        JUNO_CLIPBOARD_NAME,
        JUNO_CLIPBOARD_MARKER,
    ),
)

# Juno imports packages from Documents/site-packages.
JUNO_SITE_PACKAGES_NAME = 'site-packages'


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


def pythonista_renderer_path():
    return os.path.join(
        pythonista_documents_root(),
        PYTHONISTA_RENDERER_NAME,
    )


def pythonista_adapter_path(target=None):
    """Return the installed packaged Pythonista console adapter path."""
    root = absolute(
        target
        or pythonista_site_packages()
    )

    return os.path.join(
        root,
        'forge',
        'adapters',
        'pythonista',
        'console_ui.py',
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


def pythonista_renderer_is_portable(path):
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

    return PYTHONISTA_RENDERER_MARKER in text


def remove_owned_legacy_pythonista_renderer():
    """
    Remove the obsolete root renderer only when Portable Forge owns it.

    Foreign files with the same name are left untouched.
    """
    destination = pythonista_renderer_path()

    if not os.path.isfile(
        destination
    ):
        return False

    if not pythonista_renderer_is_portable(
        destination
    ):
        return False

    os.remove(
        destination
    )

    return True

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


def adapter_source(source_root, adapter, filename):
    """Path of one adapter file in the repository: adapters/<adapter>/<file>."""
    return os.path.join(
        absolute(source_root),
        'adapters',
        adapter,
        filename,
    )


def adapter_files_preflight(
    source_root,
    adapter,
    files,
    destination_root,
    label,
    force=False,
):
    """
    Plan copying one adapter's marked files into destination_root.

    files is a sequence of (filename, marker). Before anything is written,
    refuses a destination that is not a file, an unmarked file of the same
    name, or a different marked file without force. label names the app in
    messages, for example 'PythonIDE'. Returns one plan dict per file.
    """
    destination_root = absolute(destination_root)
    plans = []

    for filename, marker in files:
        source = adapter_source(source_root, adapter, filename)

        if not os.path.isfile(source):
            raise RuntimeError(
                '%s adapter source was not found: %s' % (label, source)
            )

        source_text = _read_text(source)

        if marker not in source_text:
            raise RuntimeError(
                '%s adapter source is missing its Portable Forge marker: %s'
                % (label, filename)
            )

        destination = os.path.join(destination_root, filename)

        if not os.path.exists(destination):
            plans.append({
                'source': source,
                'destination': destination,
                'write': True,
                'created': True,
            })
            continue

        if not os.path.isfile(destination):
            raise RuntimeError(
                'Portable Forge refuses to replace an existing '
                'non-file %s adapter path:\n%s' % (label, destination)
            )

        destination_text = _read_text(destination)

        if destination_text == source_text:
            plans.append({
                'source': source,
                'destination': destination,
                'write': False,
                'created': False,
            })
            continue

        if marker not in destination_text:
            raise RuntimeError(
                'Portable Forge refuses to overwrite an unrecognised '
                '%s adapter file:\n%s\n'
                'No %s adapter files were changed.'
                % (label, destination, label)
            )

        if not force:
            raise RuntimeError(
                'A different Portable Forge %s adapter already '
                'exists:\n%s\n'
                'Use --force only when deliberately updating this '
                'marked Portable Forge adapter.'
                % (label, destination)
            )

        plans.append({
            'source': source,
            'destination': destination,
            'write': True,
            'created': False,
        })

    return plans


def install_adapter_files(plans, destination_root):
    """Copy planned adapter files, each atomically; return every destination."""
    os.makedirs(absolute(destination_root), exist_ok=True)
    installed = []

    for plan in plans:
        destination = plan['destination']

        if plan['write']:
            temporary = destination + '.portable-forge-new'
            try:
                shutil.copyfile(plan['source'], temporary)
                os.replace(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.remove(temporary)

        installed.append(destination)

    return installed


def pythonide_adapter_source(
    source_root,
    filename,
):
    return adapter_source(source_root, 'pythonide', filename)


def pythonide_adapter_preflight(
    source_root,
    workspace,
    force=False,
):
    return adapter_files_preflight(
        source_root,
        'pythonide',
        PYTHONIDE_ADAPTER_FILES,
        workspace,
        'PythonIDE',
        force=force,
    )


def install_pythonide_adapter(
    source_root,
    workspace,
    force=False,
):
    plans = pythonide_adapter_preflight(
        source_root,
        workspace,
        force=force,
    )
    return install_adapter_files(plans, workspace)


def juno_adapter_preflight(
    source_root,
    documents,
    force=False,
):
    return adapter_files_preflight(
        source_root,
        'juno',
        JUNO_ADAPTER_FILES,
        documents,
        'Juno',
        force=force,
    )


def install_juno_adapter(
    source_root,
    documents,
    force=False,
):
    """Copy forge_entry.py and juno_clipboard.py into Juno's Documents."""
    plans = juno_adapter_preflight(
        source_root,
        documents,
        force=force,
    )
    installed = install_adapter_files(plans, documents)

    # ops/ exists so FORGE config does not warn about a missing ops root.
    os.makedirs(
        os.path.join(absolute(documents), '.forge', 'ops'),
        exist_ok=True,
    )
    return installed


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


def existing_owned_legacy_packages(target):
    """Return obsolete Portable Forge packages that this installer owns."""
    target = absolute(
        target
    )

    result = []

    for package_name in LEGACY_RUNTIME_PACKAGES:
        package_path = os.path.join(
            target,
            package_name,
        )

        if (
            os.path.exists(
                package_path
            )
            and package_is_portable_install(
                package_path
            )
        ):
            result.append(
                package_name
            )

    return result


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

    legacy_owned = existing_owned_legacy_packages(
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

    # User-owned operations live outside the replaceable runtime package.
    #
    # Forge creates this directory but never populates, replaces, or deletes
    # its contents during normal installation.
    os.makedirs(
        os.path.join(
            forge_home,
            'ops',
        ),
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

        # Remove only obsolete packages carrying Portable Forge's ownership
        # marker. Never remove an unrelated package merely because it has an
        # old Forge package name.
        for package_name in legacy_owned:
            package_path = os.path.join(
                target,
                package_name,
            )

            if os.path.isdir(
                package_path
            ):
                shutil.rmtree(
                    package_path
                )
            elif os.path.exists(
                package_path
            ):
                os.remove(
                    package_path
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
        '--pythonide-workspace',
        help=(
            'Install the runtime and PythonIDE adapter directly into '
            'this workspace. Forge home becomes WORKSPACE/.forge.'
        ),
    )

    result.add_argument(
        '--juno-documents',
        help=(
            'Install for Juno: the runtime into DOCUMENTS/site-packages, '
            'Forge home into DOCUMENTS/.forge, and the Juno adapter '
            '(forge_entry.py, juno_clipboard.py) into DOCUMENTS.'
        ),
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

    pythonide_workspace = (
        absolute(args.pythonide_workspace)
        if args.pythonide_workspace
        else None
    )

    juno_documents = (
        absolute(args.juno_documents)
        if args.juno_documents
        else None
    )

    if pythonide_workspace and juno_documents:
        raise RuntimeError(
            '--pythonide-workspace cannot be combined with '
            '--juno-documents.'
        )

    # An explicit app installation chooses its own target and Forge home.
    explicit_option = (
        '--pythonide-workspace' if pythonide_workspace
        else '--juno-documents' if juno_documents
        else None
    )

    if explicit_option:
        if args.target:
            raise RuntimeError(
                '--target cannot be combined with '
                + explicit_option + '.'
            )

        if args.home:
            raise RuntimeError(
                '--home cannot be combined with '
                + explicit_option + '.'
            )

    if pythonide_workspace:
        target = pythonide_workspace
        forge_home = os.path.join(
            pythonide_workspace,
            '.forge',
        )

    elif juno_documents:
        target = os.path.join(
            juno_documents,
            JUNO_SITE_PACKAGES_NAME,
        )
        forge_home = os.path.join(
            juno_documents,
            '.forge',
        )

    else:
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

        # An explicit PythonIDE or Juno installation takes precedence over
        # host autodetection. This avoids Pythonista-like compatibility
        # modules in another host accidentally selecting the Pythonista
        # launcher path.
        pythonista = (
            not pythonide_workspace
            and not juno_documents
            and is_pythonista()
        )

        launcher_plan = None

        if pythonista:
            launcher_plan = pythonista_launcher_preflight(
                source_root,
                force=args.force,
            )

        if pythonide_workspace:
            pythonide_adapter_preflight(
                source_root,
                pythonide_workspace,
                force=args.force,
            )

        if juno_documents:
            juno_adapter_preflight(
                source_root,
                juno_documents,
                force=args.force,
            )

        installed = install(
            source_root,
            target,
            forge_home=forge_home,
            force=args.force,
        )

        launcher = None
        pythonista_adapter = None
        legacy_renderer_removed = False
        launcher_opened = False
        launcher_open_error = ''
        launcher_should_open = False
        pythonide_files = []
        juno_files = []

        if pythonista:
            launcher = install_pythonista_launcher(
                source_root,
                force=args.force,
            )

            pythonista_adapter = pythonista_adapter_path(
                installed['target']
            )

            if not os.path.isfile(
                pythonista_adapter
            ):
                raise RuntimeError(
                    'Installed Pythonista adapter was not found: '
                    + pythonista_adapter
                )

            legacy_renderer_removed = (
                remove_owned_legacy_pythonista_renderer()
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

        if pythonide_workspace:
            pythonide_files = install_pythonide_adapter(
                source_root,
                pythonide_workspace,
                force=args.force,
            )

        if juno_documents:
            juno_files = install_juno_adapter(
                source_root,
                juno_documents,
                force=args.force,
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

        if pythonide_files:
            print(
                'PythonIDE workspace:',
                pythonide_workspace,
            )
            print(
                'PythonIDE launcher:',
                os.path.join(
                    pythonide_workspace,
                    PYTHONIDE_LAUNCHER_NAME,
                ),
            )
            print(
                'PythonIDE live UI:',
                os.path.join(
                    pythonide_workspace,
                    PYTHONIDE_LIVE_UI_NAME,
                ),
            )

        if juno_files:
            print(
                'Juno Documents:',
                juno_documents,
            )
            print(
                'Juno launcher:',
                os.path.join(
                    juno_documents,
                    JUNO_LAUNCHER_NAME,
                ),
            )
            print(
                'Juno clipboard:',
                os.path.join(
                    juno_documents,
                    JUNO_CLIPBOARD_NAME,
                ),
            )

        if launcher:
            print(
                'Pythonista launcher:',
                launcher,
            )
            if pythonista_adapter:
                print(
                    'Pythonista live UI:',
                    pythonista_adapter,
                )

            if legacy_renderer_removed:
                print(
                    'Removed legacy root Pythonista live UI:',
                    pythonista_renderer_path(),
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

        if pythonide_files:
            print(
                'Next: put a Forge bundle on the clipboard and run '
                + PYTHONIDE_LAUNCHER_NAME
            )

        elif juno_files:
            print(
                'Next: restart the Juno kernel, put a Forge bundle on the '
                'clipboard and run '
                + JUNO_LAUNCHER_NAME
            )

        elif launcher:
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