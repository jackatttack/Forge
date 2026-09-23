"""
File versions for Forge's stale-read guard.

A file's version is a short hash of its exact bytes. READ reports it, and
every successful WRITE, REPLACE, INSERT or DELETE reports the version it
left behind. A mutation may pin the version it expects with IF_VERSION;
if the file has changed, the mutation is refused with SKIPPED_STALE_READ
and the file is left untouched.

Pins are checked against a snapshot taken before the bundle runs, so
several edits to one file in a single bundle can all pin the version the
model actually read.

The refusal deliberately does not reveal the current version. The only
way to obtain a valid pin is to look at the file again.
"""

import hashlib
import os


# ----- Editable settings ------------------------------------------------

# Hex characters kept from the SHA-256 digest. Eight is ample for spotting
# change in one workspace and short enough to copy by hand.
VERSION_LENGTH = 8

# Operations that report the version they leave behind.
VERSIONED_OPS = ('WRITE', 'REPLACE', 'INSERT', 'DELETE')


# ----- Fixed vocabulary -------------------------------------------------

PIN_DIRECTIVE = 'IF_VERSION'

# Version reported for a path with no file. Pinning it means
# "only if the file does not exist yet".
MISSING = 'missing'

VERSION_PREFIX = 'v:'


def file_version(abs_path):
    """Return the short version of a file's exact bytes, or MISSING."""
    if not os.path.isfile(abs_path):
        return MISSING
    digest = hashlib.sha256()
    with open(abs_path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()[:VERSION_LENGTH]


def format_version(version):
    """Render a version the way packets show it, for example 'v:a3f9c2e1'."""
    return VERSION_PREFIX + version


def normalise_pin(value):
    """Accept '7b21d0aa', 'v:7b21d0aa' or 'missing', in any case."""
    pin = str(value or '').strip().lower()
    if pin.startswith(VERSION_PREFIX):
        pin = pin[len(VERSION_PREFIX):].strip()
    return pin


def is_versioned_op(op_name):
    return str(op_name or '').strip().upper() in VERSIONED_OPS


def target_file(ctx, target):
    """
    Return (abs_path, error) for an operation target.

    A Python target such as 'app.py::main' is versioned as its whole file.
    Named-root prefixes resolve exactly as they do for the operations.
    """
    from forge.core.file_safety import safe_target

    path = str(target or '').split('::', 1)[0].strip()
    root, abs_path, error = safe_target(ctx, path)
    return abs_path, error


def snapshot_pins(ctx, parsed_ops):
    """Return {abs_path: version} for every file a pinned op targets."""
    snapshot = {}
    for parsed_op in parsed_ops or []:
        directives = parsed_op.get('directives') or {}
        if PIN_DIRECTIVE not in directives:
            continue
        abs_path, error = target_file(ctx, parsed_op.get('target'))
        if error or abs_path in snapshot:
            continue
        snapshot[abs_path] = file_version(abs_path)
    return snapshot


def check_pin(ctx, parsed_op, snapshot):
    """
    Return None when the op is unpinned or its pin is current.

    Otherwise return the refusal message. Path errors are left for the
    operation itself to report. A file absent from the snapshot is
    versioned now, which only happens if the snapshot could not be taken.
    """
    directives = parsed_op.get('directives') or {}
    if PIN_DIRECTIVE not in directives:
        return None

    pin = normalise_pin(directives.get(PIN_DIRECTIVE))
    abs_path, error = target_file(ctx, parsed_op.get('target'))
    if error:
        return None

    current = (snapshot or {}).get(abs_path)
    if current is None:
        current = file_version(abs_path)

    if pin == current:
        return None

    return (
        'File changed since version %s was read; it was not touched. '
        'READ it again and pin the version shown in the new header.'
    ) % (pin or '(empty)')


def note_version_after(ctx, parsed_op, result):
    """Append the version a successful mutation left behind to its result."""
    try:
        abs_path, error = target_file(ctx, parsed_op.get('target'))
        if error:
            return
        version = file_version(abs_path)
    except Exception:
        return
    result['version_after'] = version
    message = str(result.get('message') or '').rstrip()
    result['message'] = message + ' · ' + format_version(version)