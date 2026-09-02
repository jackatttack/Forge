# -*- coding: utf-8 -*-
"""
WRITE Forge op.

One complete-file verb:

- missing path -> create
- existing identical file -> clean no-op
- existing different file -> explicit overwrite confirmation required
"""

import os

from forge.core.file_safety import (
    CompileBlocked,
    checked_write,
    read_text,
    record_touched,
    safe_target,
    touched_file,
    write_text,
)


SPEC = {
    'name': 'WRITE',
    'target_kind': 'path',
    'body_mode': 'required',
    'allowed_directives': set([
        'CONFIRM',
        'ALLOW_BROKEN',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Write complete file contents, creating new files or explicitly overwriting existing files.',
    'minimal_example': [
        'WRITE scratch/example.txt',
        'BEGIN_BODY',
        'hello',
        'END_BODY',
        '',
        'WRITE scratch/example.txt',
        'CONFIRM: overwrite',
        'BEGIN_BODY',
        'replacement',
        'END_BODY',
    ],
}


HINTS = {
    '_max_hints': 1,

    'body': {
        'message': 'WRITE needs complete file content.',
        'why': 'WRITE owns the whole target file, so Forge needs the full requested text.',
        'example': [
            'WRITE scratch/example.txt',
            'BEGIN_BODY',
            'hello',
            'END_BODY',
        ],
        'next': [
            'Add BEGIN_BODY / END_BODY.',
            'Use REPLACE or INSERT for surgical edits.',
        ],
    },

    'overwrite confirmation': {
        'message': 'Existing files require explicit overwrite confirmation.',
        'why': 'WRITE refuses to replace different existing content accidentally.',
        'example': [
            'WRITE scratch/example.txt',
            'CONFIRM: overwrite',
            'BEGIN_BODY',
            'replacement',
            'END_BODY',
        ],
        'next': [
            'READ the file if unsure.',
            'Use CONFIRM: overwrite only when replacing the whole file is intentional.',
        ],
    },

    'compile': {
        'message': 'WRITE refused Python that would not compile.',
        'why': 'Forge compile-checks Python before writing it.',
        'next': [
            'Fix the syntax and retry.',
            'Use ALLOW_BROKEN: yes only for deliberate broken fixtures.',
        ],
    },
}


def validate(parsed_op):
    errors = []

    if not (
        parsed_op.get('target')
        or ''
    ).strip():
        errors.append(
            'WRITE requires a target path'
        )

    if not parsed_op.get('body'):
        errors.append(
            'WRITE requires body content'
        )

    return errors


def _truthy(value):
    return str(
        value
        or ''
    ).strip().lower() in (
        'yes',
        'true',
        '1',
    )


def _overwrite_confirmed(value):
    return str(
        value
        or ''
    ).strip().lower() in (
        'overwrite',
        'yes',
        'true',
        '1',
        'confirm',
    )


def execute(ctx, parsed_op, result):
    target = (
        parsed_op.get('target')
        or ''
    ).strip()

    body = (
        parsed_op.get('body')
        or ''
    )

    directives = (
        parsed_op.get('directives')
        or {}
    )

    root, abs_path, err = safe_target(
        ctx,
        target,
    )

    if err:
        result['status'] = 'FAILED_IO'
        result['message'] = err
        return

    existed_before = os.path.exists(
        abs_path
    )

    if existed_before and not os.path.isfile(
        abs_path
    ):
        result['status'] = 'FAILED_IO'
        result['message'] = (
            'Target exists but is not a file: '
            + target
        )
        return

    before = (
        read_text(abs_path)
        if existed_before
        else ''
    )

    if existed_before and before == body:
        result['status'] = 'APPLIED'
        result['message'] = (
            'File already has requested content: '
            + target
        )
        result['file'] = target
        result['preview'] = (
            'WRITE %s\nmode: unchanged\n%d bytes'
            % (
                target,
                len(body),
            )
        )
        result['data'] = {
            'path': target,
            'bytes': len(body),
            'mode': 'unchanged',
            'changed': False,
            'existed_before': True,
        }
        return

    if (
        existed_before
        and not _overwrite_confirmed(
            directives.get('CONFIRM')
        )
    ):
        result['status'] = 'FAILED_CONFIRM'
        result['message'] = (
            'WRITE overwrite confirmation required for existing file: '
            + target
        )
        return

    allow_broken = _truthy(
        directives.get(
            'ALLOW_BROKEN'
        )
    )

    try:
        if allow_broken:
            write_text(
                abs_path,
                body,
            )
        else:
            checked_write(
                abs_path,
                body,
            )

    except CompileBlocked as e:
        result['status'] = 'FAILED_COMPILE'
        result['message'] = (
            'WRITE refused: file would not compile. '
            'Line %s: %s. File untouched. '
            'Use ALLOW_BROKEN: yes only for deliberate broken fixtures.'
            % (
                e.lineno,
                e.msg,
            )
        )
        return

    touched = touched_file(
        target,
        before,
        body,
        existed_before=existed_before,
    )

    record_touched(
        ctx,
        result,
        touched,
    )

    mode = (
        'overwrite'
        if existed_before
        else 'create'
    )

    result['status'] = 'APPLIED'
    result['message'] = (
        (
            'Overwrote file: '
            if existed_before
            else 'Created file: '
        )
        + target
    )

    result['preview'] = (
        'WRITE %s\nmode: %s\n%d bytes written'
        % (
            target,
            mode,
            len(body),
        )
    )

    result['file'] = target
    result['data'] = {
        'path': target,
        'bytes': len(body),
        'mode': mode,
        'changed': True,
        'existed_before': bool(
            existed_before
        ),
    }