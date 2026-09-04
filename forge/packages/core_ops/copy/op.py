# -*- coding: utf-8 -*-
"""
COPY operation.

Copy a project-relative text file from one path to another.

Contract:

COPY source/path.txt
TO: destination/path.txt
OVERWRITE: no|yes

Recovery model:
- source is read but not changed
- destination is recorded with its real previous state
- REVERT can restore or delete the destination
"""

import os

from forge.core.file_safety import safe_target, read_text, write_text, touched_file, record_touched


SPEC = {
    'name': 'COPY',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set(['TO', 'OVERWRITE']),
    'required_directives': set(['TO']),
}


HELP = {
    'summary': 'Copy one project-relative text file to another project-relative path.',
    'minimal_example': [
        'COPY scratch/source.py',
        'TO: scratch/copy.py',
        '',
        'COPY scratch/source.py',
        'TO: scratch/existing.py',
        'OVERWRITE: yes',
    ],
    'directives': {
        'TO': (
            'Required destination path, relative to the project root.'
        ),
        'OVERWRITE': (
            'With yes, replace an existing destination file deliberately.'
        ),
    },
    'internal_directives': [],
    'common_failures': [
        'The source does not exist or is not a regular file.',
        'The destination already exists and OVERWRITE: yes was omitted.',
        'The source or destination escapes the project root.',
        'The destination exists but is not a regular file.',
    ],
    'safe_usage': [
        'READ an existing destination before overwriting it.',
        'COPY handles one text file; it does not copy directories.',
        'Verify a copy before deleting the source during a manual move.',
    ],
    'related_ops': [
        'READ inspects the source or an existing destination.',
        'DELETE removes the source after a verified manual move.',
        'REVERT restores or removes the destination using recorded metadata.',
    ],
}


HINTS = {
    '_max_hints': 1,
    'destination exists': {
        'message': 'COPY destination exists; use OVERWRITE: yes only when replacing it deliberately.',
        'why': 'COPY protects existing files by default so accidental overwrites are reversible decisions, not surprises.',
        'example': [
            'COPY scratch/source.py',
            'TO: scratch/existing.py',
            'OVERWRITE: yes',
        ],
        'next': [
            'READ the destination first if unsure.',
            'Use OVERWRITE: yes only when the existing destination should be replaced.',
            'If the source should disappear, verify the copy and then DELETE the source deliberately.',
        ],
        'priority': 100,
    },
    'to': {
        'message': 'COPY needs TO: destination/path.',
        'why': 'The source goes on the COPY line and the destination goes in TO.',
        'example': [
            'COPY scratch/source.py',
            'TO: scratch/source_copy.py',
        ],
        'next': [
            'Add TO: with a project-relative destination path.',
        ],
        'priority': 90,
    },
    'source': {
        'message': 'COPY needs an existing source file.',
        'why': 'COPY reads the source file and writes its content to the destination.',
        'example': [
            'COPY scratch/source.py',
            'TO: scratch/source_copy.py',
        ],
        'next': [
            'Use MAP on the containing directory or SEARCH to confirm the source path.',
        ],
        'priority': 80,
    },
}


def _truthy(value):
    return str(value or '').strip().lower() in ('1', 'yes', 'y', 'true', 'on')


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if not target:
        errors.append('COPY requires a source path')

    dest = str(directives.get('TO') or '').strip()
    if not dest:
        errors.append('COPY requires TO: destination/path')

    overwrite = str(directives.get('OVERWRITE') or 'no').strip().lower()
    if overwrite not in ('', '0', '1', 'no', 'yes', 'n', 'y', 'false', 'true', 'off', 'on'):
        errors.append('COPY OVERWRITE must be yes or no')

    if target and dest and target == dest:
        errors.append('COPY source and destination must be different')

    return errors


def execute(ctx, parsed_op, result):
    source = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    dest = str(directives.get('TO') or '').strip()
    overwrite = _truthy(directives.get('OVERWRITE'))

    root, src_abs, src_err = safe_target(ctx, source)
    if src_err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = src_err
        return

    root, dest_abs, dest_err = safe_target(ctx, dest)
    if dest_err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = dest_err
        return

    if not os.path.isfile(src_abs):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'Source file not found: ' + source
        return

    dest_existed = os.path.exists(dest_abs)
    if dest_existed and not os.path.isfile(dest_abs):
        result['status'] = 'FAILED_IO'
        result['message'] = 'Destination exists but is not a file: ' + dest
        return

    if dest_existed and not overwrite:
        result['status'] = 'FAILED_EXISTS'
        result['message'] = 'Destination exists; use OVERWRITE: yes'
        return

    try:
        source_text = read_text(src_abs)
        before_dest = read_text(dest_abs) if dest_existed else ''
    except Exception as e:
        result['status'] = 'FAILED_IO'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    try:
        write_text(dest_abs, source_text)
    except Exception as e:
        result['status'] = 'FAILED_IO'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        return

    touched = touched_file(dest, before_dest, source_text, existed_before=bool(dest_existed))
    record_touched(ctx, result, touched)

    result['status'] = 'APPLIED'
    result['message'] = 'Copied %s -> %s' % (source, dest)
    result['file'] = dest
    result['preview'] = result['message']
    result['data'] = {
        'source': source,
        'destination': dest,
        'overwrite': bool(overwrite),
        'destination_existed': bool(dest_existed),
    }
