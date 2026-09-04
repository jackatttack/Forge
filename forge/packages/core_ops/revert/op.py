# -*- coding: utf-8 -*-
"""
REVERT Forge op.

Restore project-owned touched files from a stored Forge run.
"""


SPEC = {
    'name': 'REVERT',
    'target_kind': 'none',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'ARGS',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Restore project files to their pre-run state using a stored Forge run.',
    'minimal_example': [
        'FORGE runs latest',
        '',
        'DIFF 20260831_120000',
        '',
        'REVERT 20260831_120000',
    ],
    'directives': {},
    'internal_directives': [
        'ARGS',
    ],
    'common_failures': [
        'Omitting the explicit stored-run stamp.',
        'Passing latest instead of the stamp reported by FORGE runs latest.',
        'Expecting REVERT to restore only one file from a multi-file run.',
        'Assuming REVERT refuses when the current disk has drifted.',
    ],
    'safe_usage': [
        'Inspect the target run with DIFF <stamp> before recovering.',
        'Preserve newer work separately before reverting a drifted file.',
        'Treat REVERT as a whole-run recovery operation.',
        'Check a failed result because restoration may have been partial.',
    ],
    'related_ops': ['BRANCH', 'DIFF', 'FORGE'],
}


HINTS = {
    '_max_hints': 1,

    'run': {
        'message': 'REVERT needs a stored run id.',
        'why': 'Forge uses the recovery snapshots stored with that run.',
        'example': [
            'FORGE runs latest',
            '',
            'REVERT 20260831_120000',
        ],
        'next': [
            'Use FORGE runs to locate the stamp.',
            'Use DIFF <stamp> first if unsure.',
        ],
    },
}


def validate(parsed_op):
    args = (
        (
            parsed_op.get(
                'directives'
            )
            or {}
        ).get('ARGS')
        or parsed_op.get(
            'target'
        )
        or ''
    ).strip()

    if not args:
        return [
            'REVERT requires a run stamp'
        ]

    return []


def execute(ctx, parsed_op, result):
    from forge.core.environment import path_from_ctx
    from forge.core.run_storage import revert_run

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

    args = (
        (
            parsed_op.get(
                'directives'
            )
            or {}
        ).get('ARGS')
        or parsed_op.get(
            'target'
        )
        or ''
    ).strip()

    ok, msg = revert_run(
        project_root,
        args,
        mode=run_mode,
        environment=environment,
    )

    result['status'] = (
        'APPLIED'
        if ok
        else 'FAILED_IO'
    )

    result['message'] = msg