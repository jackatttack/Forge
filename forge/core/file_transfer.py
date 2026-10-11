# -*- coding: utf-8 -*-
"""
Shared transfer engine for COPY and MOVE.

A transfer copies one file, or a whole directory tree, from a source path to
a destination path. Either path may carry a named-root prefix such as
"icloud:", so transfers work across roots in both directions.

TO always names the destination itself, never a folder to copy "into":

    COPY a/game
    TO: b/game          b/game becomes a copy of a/game

Every transfer runs in two phases:

    plan    Resolve paths, list files, apply filters, and check conflicts,
            protected paths, the file limit and byte-exact snapshots.
            Nothing is written. Any problem refuses the whole transfer.
    apply   Write destination files, remove destination extras for
            OVERWRITE: replace, and for MOVE verify every copy before
            removing the sources and any source directories left empty.

Every file created, replaced or removed is recorded through record_touched,
so the packet's Changed files, DIFF and REVERT all cover it. Directories are
not recorded: reverting a transfer removes created files but leaves any
folders it created, exactly as with WRITE.

All ordinary files are transferred byte-for-byte. Binary and large-file
snapshots are streamed to temporary storage and persisted with the run.
Each destination write is staged and verified before atomic replacement.
Observable source and destination drift is refused; this is not a lock
against concurrent writers or a crash-atomic multi-file transaction.
"""

import fnmatch
import os

from forge.core.core_guard import has_confirm, target_is_protected
from forge.core.file_safety import (
    record_touched,
    safe_target,
    split_root_prefix,
    touched_file,
)


# --- policies you may tune ---------------------------------------------------

# File and directory names skipped at any depth, matched with shell-style
# wildcards. EXCLUDE adds to these; EXCLUDE: none switches them off.
DEFAULT_EXCLUDES = ('__pycache__', '*.pyc', '.DS_Store', 'script_snapshots')

# A transfer that would change more files than this needs CONFIRM: yes.
# DRY_RUN never needs confirmation because it changes nothing.
FILE_LIMIT = 200

# How many planned changes the packet preview lists before summarising.
PREVIEW_LIMIT = 40

# How many offending paths a refusal names before summarising.
REFUSAL_LIMIT = 10


# --- vocabulary --------------------------------------------------------------

TRUE_WORDS = ('1', 'yes', 'y', 'true', 'on')
FALSE_WORDS = ('', '0', 'no', 'n', 'false', 'off')

ACTION_SYMBOLS = {
    'create': '+',
    'replace': '~',
    'unchanged': '=',
    'remove': '-',
}


class TransferRefused(Exception):
    """The plan found a problem. Nothing has been written."""

    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


class PlannedFile(object):
    """One immutable source snapshot and its expected destination state."""

    def __init__(self, relative, source_path, destination_path, content,
                 destination_existed, destination_before):
        self.relative = relative
        self.source_path = source_path
        self.destination_path = destination_path
        self.content = content
        self.destination_existed = destination_existed
        self.destination_before = destination_before

    @property
    def action(self):
        from .file_content import same_content
        if not self.destination_existed:
            return 'create'
        if same_content(self.destination_before, self.content):
            return 'unchanged'
        return 'replace'


class PlannedRemoval(object):
    """A destination file that OVERWRITE: replace removes."""

    def __init__(self, relative, destination_path, before):
        self.relative = relative
        self.destination_path = destination_path
        self.before = before


class TransferPlan(object):
    """Everything a transfer will do, decided before anything is written."""

    def __init__(self, op_name, source, destination, options):
        self.op_name = op_name
        self.source = source
        self.destination = destination
        self.options = options
        self.source_root_name, self.source_base = split_root_prefix(source)
        self.destination_root_name, self.destination_base = split_root_prefix(
            destination
        )
        self.source_path = ''
        self.destination_path = ''
        self.is_directory = False
        self.files = []
        self.removals = []
        self.filtered = []
        self.removed_directories = 0
        self.completed = 0

    @property
    def is_move(self):
        return self.op_name == 'MOVE'

    def source_rel(self, relative):
        return _under(self.source_base, relative)

    def destination_rel(self, relative):
        return _under(self.destination_base, relative)

    def count(self, action):
        return sum(1 for planned in self.files if planned.action == action)

    def change_count(self):
        """Files this transfer writes, removes, or (for MOVE) clears at source."""
        writes = len(self.files) - self.count('unchanged')
        sources = len(self.files) if self.is_move else 0
        return writes + len(self.removals) + sources


# --- directives --------------------------------------------------------------

def validate_transfer(op_name, parsed_op):
    """Return the directive errors shared by COPY and MOVE."""
    errors = []
    source = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    destination = str(directives.get('TO') or '').strip()

    if not source:
        errors.append('%s requires a source path' % op_name)
    if not destination:
        errors.append('%s requires TO: destination/path' % op_name)
    if source and destination and source == destination:
        errors.append('%s source and destination must be different' % op_name)
    if _policy(directives.get('OVERWRITE')) is None:
        errors.append('%s OVERWRITE must be no, yes or replace' % op_name)

    dry_run = _word(directives.get('DRY_RUN'))
    if dry_run not in TRUE_WORDS and dry_run not in FALSE_WORDS:
        errors.append('%s DRY_RUN must be yes or no' % op_name)

    return errors


def read_options(parsed_op):
    """Turn validated directives into transfer options."""
    directives = parsed_op.get('directives') or {}
    return {
        'destination': str(directives.get('TO') or '').strip(),
        'policy': _policy(directives.get('OVERWRITE')) or 'no',
        'include': _pattern_list(directives.get('GLOB')),
        'exclude': _exclude_list(directives.get('EXCLUDE')),
        'dry_run': _word(directives.get('DRY_RUN')) in TRUE_WORDS,
        'confirmed': has_confirm(parsed_op),
    }


# --- the transfer ------------------------------------------------------------

def execute_transfer(ctx, parsed_op, result, op_name):
    """Plan snapshots first, then apply changes with per-file atomic writes."""
    from .content_records import run_content_store
    source = (parsed_op.get('target') or '').strip()
    options = read_options(parsed_op)
    options['content_store'] = run_content_store(ctx['run'])

    try:
        plan = build_plan(ctx, op_name, source, options)
    except TransferRefused as refusal:
        result['status'] = refusal.status
        result['message'] = refusal.message
        return
    except (OSError, ValueError) as error:
        result['status'] = 'FAILED_IO'
        result['message'] = '%s planning refused before mutation: %s' % (
            op_name, error,
        )
        return

    if options['dry_run']:
        _report(result, plan, dry_run=True)
        return

    try:
        apply_plan(ctx, plan, result)
    except (OSError, ValueError) as error:
        result['status'] = 'FAILED_IO'
        result['message'] = (
            '%s stopped after %d recorded change(s): %s: %s. '
            'REVERT this run to undo the recorded part.'
            % (op_name, plan.completed, type(error).__name__, error)
        )
        return

    _report(result, plan, dry_run=False)


def build_plan(ctx, op_name, source, options):
    """Decide the whole transfer without writing anything."""
    plan = TransferPlan(op_name, source, options['destination'], options)

    if not plan.source_base or not plan.destination_base:
        raise TransferRefused(
            'FAILED_INVALID_PATH',
            '%s cannot transfer a whole root; name a path inside it' % op_name,
        )

    plan.source_path = _resolve(ctx, plan.source)
    plan.destination_path = _resolve(ctx, plan.destination)

    if os.path.islink(plan.source_path):
        raise TransferRefused(
            'FAILED_INVALID_PATH', 'Symlinks are not transferred: ' + source,
        )
    if not os.path.exists(plan.source_path):
        raise TransferRefused('FAILED_NOT_FOUND', 'Source not found: ' + source)
    if os.path.islink(plan.destination_path):
        raise TransferRefused(
            'FAILED_INVALID_PATH',
            'Destination is a symlink: ' + plan.destination,
        )

    _refuse_overlap(plan)

    plan.is_directory = os.path.isdir(plan.source_path)
    if plan.is_directory:
        _plan_directory(plan)
    elif os.path.isfile(plan.source_path):
        _plan_single_file(plan)
    else:
        raise TransferRefused(
            'FAILED_IO',
            'Source is not an ordinary file or directory: ' + source,
        )

    _check_protection(plan)
    _check_file_limit(plan)
    return plan


def apply_plan(ctx, plan, result):
    """Install exact snapshots, then verify all copies before source removal."""
    from .file_content import atomic_install, text_content
    destination_root = plan.destination_root_name or ''
    source_root = plan.source_root_name or ''
    empty = text_content('')

    for planned in plan.files:
        if planned.action == 'unchanged':
            continue

        def recheck_destination():
            _assert_state(
                planned.destination_path, planned.destination_existed,
                planned.destination_before,
            )

        atomic_install(
            planned.destination_path, planned.content,
            before_replace=recheck_destination,
        )
        _record(
            ctx, result, plan,
            plan.destination_rel(planned.relative), destination_root,
            planned.destination_before, planned.content,
            existed_before=planned.destination_existed, existed_after=True,
        )

    for removal in plan.removals:
        _assert_state(removal.destination_path, True, removal.before)
        os.remove(removal.destination_path)
        _record(
            ctx, result, plan,
            plan.destination_rel(removal.relative), destination_root,
            removal.before, empty,
            existed_before=True, existed_after=False,
        )

    if not plan.is_move:
        return

    # Check the entire set before deleting any source. An unchanged
    # destination still needs verification because another writer may edit it.
    for planned in plan.files:
        _assert_state(planned.destination_path, True, planned.content)
        _assert_state(planned.source_path, True, planned.content)

    for planned in plan.files:
        # Recheck immediately before this removal as well. These checks do
        # not lock out concurrent writers; they refuse observable drift.
        _assert_state(planned.destination_path, True, planned.content)
        _assert_state(planned.source_path, True, planned.content)
        os.remove(planned.source_path)
        _record(
            ctx, result, plan,
            plan.source_rel(planned.relative), source_root,
            planned.content, empty,
            existed_before=True, existed_after=False,
        )

    if plan.is_directory:
        plan.removed_directories = _remove_empty_directories(plan.source_path)


# --- planning ----------------------------------------------------------------

def _resolve(ctx, path):
    root, absolute, error = safe_target(ctx, path)
    if error:
        raise TransferRefused('FAILED_INVALID_PATH', error)
    return absolute


def _refuse_overlap(plan):
    source = os.path.realpath(plan.source_path)
    destination = os.path.realpath(plan.destination_path)

    if source == destination:
        raise TransferRefused(
            'FAILED_INVALID_PATH', 'Source and destination are the same path',
        )
    if destination.startswith(source + os.sep):
        raise TransferRefused(
            'FAILED_INVALID_PATH', 'Destination is inside the source',
        )
    if source.startswith(destination + os.sep):
        raise TransferRefused(
            'FAILED_INVALID_PATH', 'Source is inside the destination',
        )


def _plan_single_file(plan):
    if os.path.isdir(plan.destination_path):
        raise TransferRefused(
            'FAILED_EXISTS',
            'Destination is a directory; TO names the new file path itself: '
            + plan.destination,
        )

    store = plan.options['content_store']
    content = store.capture(plan.source_path)
    existed, before = _destination_state(
        plan.destination_path, plan.destination, store,
    )
    planned = PlannedFile(
        '', plan.source_path, plan.destination_path, content, existed, before,
    )
    if planned.action == 'replace' and plan.options['policy'] == 'no':
        raise TransferRefused(
            'FAILED_EXISTS', 'Destination exists; use OVERWRITE: yes',
        )
    plan.files.append(planned)


def _plan_directory(plan):
    options = plan.options
    store = options['content_store']

    if (
        os.path.exists(plan.destination_path)
        and not os.path.isdir(plan.destination_path)
    ):
        raise TransferRefused(
            'FAILED_EXISTS',
            'Destination exists but is not a directory: ' + plan.destination,
        )

    conflicts = []
    planned_relatives = set()
    for relative, source_file in _walk(
        plan.source_path, options, plan.filtered, 'source',
    ):
        content = store.capture(source_file)
        destination_file = os.path.join(
            plan.destination_path, *relative.split('/')
        )
        existed, before = _destination_state(destination_file, relative, store)
        planned = PlannedFile(
            relative, source_file, destination_file, content, existed, before,
        )
        if planned.action == 'replace' and options['policy'] == 'no':
            conflicts.append(relative)
        plan.files.append(planned)
        planned_relatives.add(relative)

    if options['policy'] == 'replace' and os.path.isdir(plan.destination_path):
        for relative, destination_file in _walk(
            plan.destination_path, options, None, 'destination',
        ):
            if relative not in planned_relatives:
                plan.removals.append(PlannedRemoval(
                    relative, destination_file, store.capture(destination_file),
                ))

    if conflicts:
        raise TransferRefused(
            'FAILED_EXISTS',
            'Destination exists for %d file(s): %s. Use OVERWRITE: yes or '
            'OVERWRITE: replace.' % (len(conflicts), _name_some(conflicts)),
        )


def _destination_state(path, label, store):
    """Snapshot an existing regular destination, preserving absence explicitly."""
    from .file_content import text_content
    if os.path.islink(path):
        raise TransferRefused(
            'FAILED_INVALID_PATH', 'Destination is a symlink: ' + label,
        )
    if not os.path.lexists(path):
        return False, text_content('')
    if not os.path.isfile(path):
        raise TransferRefused(
            'FAILED_EXISTS', 'Destination path is not a file: ' + label,
        )
    return True, store.capture(path)


def _walk(top, options, filtered, label):
    """Yield (relative, full_path) for every kept file, in sorted order."""
    for folder, directory_names, file_names in os.walk(top):
        folder_relative = os.path.relpath(folder, top)

        kept = []
        for name in sorted(directory_names):
            relative = _join(folder_relative, name)
            if _matches(name, options['exclude']):
                if filtered is not None:
                    filtered.append(relative + '/')
                continue
            if os.path.islink(os.path.join(folder, name)):
                raise TransferRefused(
                    'FAILED_INVALID_PATH',
                    'Symlinks are not transferred (%s): %s' % (label, relative),
                )
            kept.append(name)
        directory_names[:] = kept

        for name in sorted(file_names):
            relative = _join(folder_relative, name)
            full_path = os.path.join(folder, name)

            skipped = _matches(name, options['exclude']) or (
                options['include'] and not _matches(name, options['include'])
            )
            if skipped:
                if filtered is not None:
                    filtered.append(relative)
                continue
            if os.path.islink(full_path):
                raise TransferRefused(
                    'FAILED_INVALID_PATH',
                    'Symlinks are not transferred (%s): %s' % (label, relative),
                )
            if not os.path.isfile(full_path):
                raise TransferRefused(
                    'FAILED_IO',
                    'Not an ordinary file (%s): %s' % (label, relative),
                )
            yield relative, full_path


def _check_protection(plan):
    """Require CONFIRM when the transfer changes a protected core path."""
    if plan.options['confirmed']:
        return

    changed = []
    if plan.destination_root_name is None:
        changed.extend(plan.destination_rel(p.relative) for p in plan.files)
        changed.extend(plan.destination_rel(r.relative) for r in plan.removals)
    if plan.is_move and plan.source_root_name is None:
        changed.extend(plan.source_rel(p.relative) for p in plan.files)

    protected = [path for path in changed if target_is_protected(path)]
    if protected:
        raise TransferRefused(
            'FAILED_NEEDS_CONFIRM',
            'Protected core paths need CONFIRM: yes: ' + _name_some(protected),
        )


def _check_file_limit(plan):
    options = plan.options
    count = plan.change_count()
    if count > FILE_LIMIT and not options['confirmed'] and not options['dry_run']:
        raise TransferRefused(
            'FAILED_NEEDS_CONFIRM',
            '%s would change %d files (limit %d). Check it with DRY_RUN: yes, '
            'narrow it with GLOB or EXCLUDE, or add CONFIRM: yes.'
            % (plan.op_name, count, FILE_LIMIT),
        )


# --- reporting ---------------------------------------------------------------

def _report(result, plan, dry_run):
    counts = {
        'created': plan.count('create'),
        'replaced': plan.count('replace'),
        'unchanged': plan.count('unchanged'),
        'removed': len(plan.removals),
        'filtered': len(plan.filtered),
    }
    summary = '%d created, %d replaced, %d unchanged, %d removed' % (
        counts['created'], counts['replaced'],
        counts['unchanged'], counts['removed'],
    )
    if plan.is_move:
        summary += ', %d source file(s) %s' % (
            len(plan.files), 'to remove' if dry_run else 'removed',
        )

    route = '%s -> %s' % (plan.source, plan.destination)
    if dry_run:
        message = 'Dry run, nothing written. %s %s would give: %s' % (
            plan.op_name, route, summary,
        )
    else:
        verb = 'Moved' if plan.is_move else 'Copied'
        message = '%s %s: %s' % (verb, route, summary)

    lines = [
        '%s %s%s' % (plan.op_name, route, '  [DRY RUN]' if dry_run else ''),
        'mode: %s · overwrite: %s' % (
            'directory' if plan.is_directory else 'file',
            plan.options['policy'],
        ),
        summary,
    ]
    if plan.filtered:
        lines.append('filtered out: %d (%s)' % (
            len(plan.filtered), _name_some(plan.filtered),
        ))
    if plan.removed_directories:
        lines.append(
            'empty source directories removed: %d' % plan.removed_directories
        )

    changes = [
        (ACTION_SYMBOLS[p.action], p.relative or plan.destination)
        for p in plan.files if p.action != 'unchanged'
    ]
    changes += [(ACTION_SYMBOLS['remove'], r.relative) for r in plan.removals]
    for symbol, name in changes[:PREVIEW_LIMIT]:
        lines.append('  %s %s' % (symbol, name))
    if len(changes) > PREVIEW_LIMIT:
        lines.append('  ... %d more' % (len(changes) - PREVIEW_LIMIT))

    data = dict(counts)
    data.update({
        'source': plan.source,
        'destination': plan.destination,
        'mode': 'directory' if plan.is_directory else 'file',
        'overwrite': plan.options['policy'],
        'dry_run': bool(dry_run),
        'files': len(plan.files),
        'removed_directories': plan.removed_directories,
    })
    if not plan.is_directory and plan.files:
        data['destination_existed'] = bool(plan.files[0].destination_existed)

    result['status'] = 'APPLIED'
    result['message'] = message
    result['file'] = plan.destination
    result['preview'] = '\n'.join(lines)
    result['data'] = data


# --- small helpers -----------------------------------------------------------

def _record(ctx, result, plan, relative, root_name, before, after,
            existed_before, existed_after):
    from .content_records import content_change
    record_touched(ctx, result, content_change(
        relative, before, after,
        existed_before=existed_before, existed_after=existed_after,
        root=root_name,
    ))
    plan.completed += 1


def _assert_state(path, existed, content):
    """Refuse observable drift or file-type substitution before mutation."""
    from .file_content import matches_file
    if not existed:
        if os.path.lexists(path):
            raise OSError('Destination appeared since planning: ' + path)
        return
    if not os.path.lexists(path) or not matches_file(path, content):
        raise OSError('File changed since planning: ' + path)





def _remove_empty_directories(top):
    """Remove directories under (and including) top that are now empty."""
    removed = 0
    for folder, _, _ in os.walk(top, topdown=False):
        if not os.listdir(folder):
            os.rmdir(folder)
            removed += 1
    return removed


def _under(base, relative):
    if not relative:
        return base
    if not base:
        return relative
    return base.rstrip('/') + '/' + relative


def _join(folder_relative, name):
    if folder_relative in ('', '.'):
        return name
    return folder_relative.replace(os.sep, '/') + '/' + name


def _matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def _name_some(paths):
    shown = ', '.join(paths[:REFUSAL_LIMIT])
    if len(paths) > REFUSAL_LIMIT:
        shown += ' and %d more' % (len(paths) - REFUSAL_LIMIT)
    return shown


def _word(value):
    return str(value or '').strip().lower()


def _policy(value):
    word = _word(value)
    if word in TRUE_WORDS:
        return 'yes'
    if word in FALSE_WORDS:
        return 'no'
    if word == 'replace':
        return 'replace'
    return None


def _pattern_list(value):
    return [part.strip() for part in str(value or '').split(',') if part.strip()]


def _exclude_list(value):
    patterns = _pattern_list(value)
    if [pattern.lower() for pattern in patterns] == ['none']:
        return []
    return list(DEFAULT_EXCLUDES) + patterns