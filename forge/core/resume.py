# -*- coding: utf-8 -*-
"""
FORGE resume <stamp>: carry on a partly applied run from the op that failed.

A bundle that fails part-way leaves its earlier operations applied and its
later ones skipped. Resending the whole bundle would repeat the applied
work, and writing a second bundle for the remainder means working it out
again by hand. Resume replays the stored bundle instead: the operations
that already applied are carried over without running, and everything from
the first one that did not apply runs.

The usual sequence:

1. A run finishes FAILED and its packet carries a Resume: line.
2. Fix the cause. If the failing operation itself was wrong, repair it in
   the stored bundle with REPLACE (the Resume: line names the file). If the
   bundle was right and the project was wrong (a failing test behind
   STOP_ON_FAIL), fix the project with an ordinary bundle.
3. Send FORGE resume <stamp> as the whole bundle.

Rules, all checked before anything runs:

- Only a FAILED run with one place to carry on from can resume: after its
  first operation that did not apply, nothing but read-only operations
  applied. A run that carried on changing things after a failure (a
  failing RUN that was not a gate) has no such place.
- The operations that already applied must be unchanged in the stored
  bundle. They are not run again, so editing them would make the packet
  describe work that never happened.

The resumed run is a new run with its own stamp. Its packet lists every
operation of the bundle, and the carried ones say which run applied them.
If it fails again it can be resumed in turn.
"""

import json
import os
import re


# ----- Fixed vocabulary -------------------------------------------------

# "FORGE resume <stamp>" as the whole bundle. Handled before parsing, like
# FORGE rerun, so the resumed run is an ordinary new run with its own stamp.
_RESUME_LINE = re.compile(r'^FORGE[ \t]+resume(?:[ \t]+(\S+))?$')

# Only a run that applied part of its bundle can be carried on.
RESUMABLE_STATUS = 'FAILED'

APPLIED = 'APPLIED'


# ----- Recognising the command ------------------------------------------

def resume_stamp(bundle_text):
    """Return the stamp named by a whole-bundle FORGE resume line, else None.

    Returns '' for a resume line with no stamp, so the caller can say so.
    """
    lines = [
        line
        for line in str(bundle_text or '').splitlines()
        if line.strip()
    ]
    if len(lines) != 1:
        return None
    match = _RESUME_LINE.match(lines[0].strip())
    if match is None:
        return None
    return match.group(1) or ''


# ----- Where a run can carry on -----------------------------------------

def _status(result):
    return str((result or {}).get('status') or '').strip().upper()


def describe_op(parsed_op):
    """'REPLACE app.py::main', or 'GIT upload' for a targetless op."""
    parsed_op = parsed_op or {}
    detail = (
        parsed_op.get('target')
        or (parsed_op.get('directives') or {}).get('ARGS')
        or ''
    )
    return ('%s %s' % (parsed_op.get('op') or '?', detail)).strip()


def is_read_only(parsed_op):
    """True when the op only inspects, by its declared effect."""
    from forge.core.operation_policy import resolve_policy
    from forge.core.registry import get_op

    op_module = get_op((parsed_op or {}).get('op'))
    return resolve_policy(op_module, parsed_op)['runs_after_failure']


def resume_point(parsed_ops, results, reads=is_read_only):
    """Return (index, problem) for where a run can carry on.

    index counts the leading operations that applied and are carried over;
    the operation at that position is the first to run again. problem is ''
    when the run can resume, else the reason it cannot, worded to follow
    "Run <stamp> cannot be resumed: ".
    """
    parsed_ops = parsed_ops or []
    results = results or []

    if not results or len(results) != len(parsed_ops):
        return 0, 'its stored record does not hold one result per operation'

    first = None
    for index, result in enumerate(results):
        if _status(result) != APPLIED:
            first = index
            break
    if first is None:
        return 0, 'every operation applied, so nothing is left to run'

    for index in range(first + 1, len(results)):
        applied = _status(results[index]) == APPLIED
        if applied and not reads(parsed_ops[index]):
            return 0, (
                'it carried on after its first failure (operation %d, %s, '
                'still applied), so there is no single place to carry on '
                'from' % (index + 1, describe_op(parsed_ops[index]))
            )

    unfinished = [
        parsed_ops[index]
        for index in range(first, len(results))
        if _status(results[index]) != APPLIED
    ]
    if all(reads(parsed_op) for parsed_op in unfinished):
        return 0, 'only read-only operations failed; send those again'

    return first, ''


def _same_operation(first, second):
    def key(parsed_op):
        parsed_op = parsed_op or {}
        return json.dumps(
            {
                'op': parsed_op.get('op') or '',
                'target': parsed_op.get('target') or '',
                'directives': parsed_op.get('directives') or {},
                'body': parsed_op.get('body') or '',
                'blocks': parsed_op.get('blocks') or {},
            },
            sort_keys=True,
        )

    return key(first) == key(second)


def changed_prefix_problem(parsed_ops, carried):
    """Return why the carried operations no longer match the bundle, or ''."""
    parsed_ops = parsed_ops or []
    expected = carried.get('parsed_ops') or []
    stamp = carried.get('stamp') or '?'

    for index, original in enumerate(expected):
        unchanged = (
            index < len(parsed_ops)
            and _same_operation(parsed_ops[index], original)
        )
        if not unchanged:
            return (
                'Operation %d (%s) already applied in run %s, but the stored '
                'bundle no longer matches it. Applied operations are not run '
                'again, so they must stay as they were: undo that edit, or '
                'send a fresh bundle for the change.'
                % (index + 1, describe_op(original), stamp)
            )
    return ''


# ----- Stored runs -------------------------------------------------------

def bundle_origin(record, stamp):
    """Return the run whose bundle.txt holds the text this run executed.

    A rerun or a resumed run stores only its one-line command; the bundle
    it ran belongs to the run it names.
    """
    record = record or {}
    return str(
        record.get('bundle_origin')
        or record.get('rerun_of')
        or stamp
        or ''
    )


def _stored_run(stamp, project_root, environment, mode):
    from forge.core import run_storage

    text = run_storage.read_text(
        project_root,
        stamp,
        'run.json',
        mode=mode,
        environment=environment,
    )
    if not text:
        return None
    try:
        record = json.loads(text)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def load(stamp, project_root=None, environment=None, mode='dev'):
    """Return what FORGE resume <stamp> needs to carry the run on.

    Keys: text (the stored bundle, ENV: header and fence removed),
    bundle_app, origin (the run holding that bundle) and carried (the
    operations that already applied, for the engine). Raises ValueError,
    with the next step, when the run cannot be resumed.
    """
    from forge.core import run_storage
    from forge.core.preparse import (
        rerun_stamp,
        take_env_header,
        unwrap_fenced_bundle,
    )

    if not stamp:
        raise ValueError(
            'FORGE resume needs a run stamp: FORGE resume <stamp>. '
            'FORGE runs lists recent runs.'
        )

    record = _stored_run(stamp, project_root, environment, mode)
    if record is None:
        raise ValueError(
            'No stored run %s to resume. FORGE runs lists recent runs.'
            % stamp
        )

    origin = bundle_origin(record, stamp)
    status = str(record.get('status') or 'UNKNOWN')

    if status == 'FAILED_PARSE' and record.get('resume_of'):
        earlier = record.get('resume_of')
        raise ValueError(
            'Run %s was a FORGE resume %s that was refused before anything '
            'ran. Fix what it reported and send FORGE resume %s again.'
            % (stamp, earlier, earlier)
        )
    if status == 'FAILED_PARSE':
        raise ValueError(
            'Run %s was refused before anything ran, so there is nothing to '
            'carry on from. Repair its bundle and send FORGE rerun %s.'
            % (stamp, origin)
        )
    if status != RESUMABLE_STATUS:
        raise ValueError(
            'Run %s finished %s. FORGE resume carries on only FAILED runs '
            'that applied part of their bundle.' % (stamp, status)
        )

    parsed_ops = record.get('parsed_ops') or []
    results = record.get('results') or []
    index, problem = resume_point(parsed_ops, results)
    if problem:
        raise ValueError(
            'Run %s cannot be resumed: %s. Send a fresh bundle for what is '
            'left.' % (stamp, problem)
        )

    stored = run_storage.read_text(
        project_root,
        origin,
        'bundle.txt',
        mode=mode,
        environment=environment,
    )
    if stored is None or not stored.strip():
        raise ValueError(
            'No stored bundle for run %s. FORGE runs lists recent runs.'
            % origin
        )

    text, bundle_app = take_env_header(stored)
    fenced = unwrap_fenced_bundle(text)
    if fenced is not None:
        text = fenced[0]
        if bundle_app is None:
            text, bundle_app = take_env_header(text)

    if rerun_stamp(text) is not None or resume_stamp(text) is not None:
        raise ValueError(
            'The stored bundle of run %s is itself a FORGE rerun or resume '
            'line, not the bundle to carry on. Send a fresh bundle for what '
            'is left.' % origin
        )

    return {
        'text': text,
        'bundle_app': bundle_app,
        'origin': origin,
        'carried': {
            'stamp': stamp,
            'parsed_ops': parsed_ops[:index],
            'results': results[:index],
            'pin_snapshot': record.get('pin_snapshot') or {},
        },
    }


# ----- The packet's Resume: line -----------------------------------------

def _shown_bundle_path(project_root, stamp, environment, mode):
    """Return a stored bundle's path, ready to paste into a REPLACE.

    Shown through the longest configured named root containing it
    (normally forge_home:), and absolute otherwise.
    """
    from forge.core import run_storage

    run_dir = run_storage._run_dir(
        project_root,
        stamp,
        mode=mode,
        environment=environment,
    )
    path = os.path.abspath(os.path.join(run_dir, 'bundle.txt'))

    best_name, best_root = '', ''
    for name, root in ((environment or {}).get('roots') or {}).items():
        root = os.path.abspath(str(root or ''))
        inside = path.startswith(root.rstrip(os.sep) + os.sep)
        if root and inside and len(root) > len(best_root):
            best_name, best_root = name, root

    if best_name:
        return '%s:%s' % (
            best_name,
            os.path.relpath(path, best_root).replace(os.sep, '/'),
        )
    return path


def resume_reference(run, environment, mode):
    """Return the Resume: text for a stored FAILED run, or ''.

    Empty when the run has no single place to carry on from, so the line
    appears only when FORGE resume would be accepted.
    """
    run = run or {}
    if str(run.get('status') or '') != RESUMABLE_STATUS:
        return ''

    parsed_ops = run.get('parsed_ops') or []
    index, problem = resume_point(parsed_ops, run.get('results') or [])
    if problem:
        return ''

    stamp = run.get('stamp') or ''
    if not stamp:
        return ''

    shown = _shown_bundle_path(
        run.get('project_root'),
        bundle_origin(run, stamp),
        environment,
        mode,
    )
    return (
        'FORGE resume %s carries on at op %d of %d (%s). To change an op '
        'first, REPLACE %s and end that bundle with the FORGE resume line'
        % (
            stamp,
            index + 1,
            len(parsed_ops),
            describe_op(parsed_ops[index]),
            shown,
        )
    )