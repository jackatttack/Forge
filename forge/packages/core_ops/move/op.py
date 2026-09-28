# -*- coding: utf-8 -*-
"""
MOVE operation.

Move one file or a whole directory tree, within a root or across named
roots. MOVE shares COPY's engine (forge.core.file_transfer): it plans the
complete move and refuses it before writing if anything is wrong, copies
every file, verifies each copy against its source, and only then removes
the sources and any source directories left empty.

Every destination file and every removed source is recorded, so REVERT puts
the sources back (recreating their directories) and removes the copies.

Contract:

    MOVE source/path
    TO: destination/path
    OVERWRITE: no|yes|replace
    GLOB: *.py, *.md
    EXCLUDE: build, *.log
    DRY_RUN: yes
    CONFIRM: yes
"""

from forge.core.file_transfer import execute_transfer, validate_transfer


SPEC = {
    'name': 'MOVE',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'TO', 'OVERWRITE', 'GLOB', 'EXCLUDE', 'DRY_RUN', 'CONFIRM',
    ]),
    'required_directives': set(['TO']),
}


HELP = {
    'summary': (
        'Move a file or a whole directory, within a root or across named roots.'
    ),
    'brief': (
        'MOVE source with TO: destination (the new path itself; icloud: ok) · '
        'copies, verifies, then removes the source · same directives as COPY.'
    ),
    'minimal_example': [
        'MOVE scratch/old_name.py',
        'TO: scratch/new_name.py',
        '',
        'MOVE icloud:projects/old_game/game',
        'TO: icloud:projects/maths_games/games/multiple_merge',
        'DRY_RUN: yes',
    ],
    'directives': {
        'TO': (
            'Required destination: the new file or directory path itself, '
            'never a folder to move into. A root prefix such as icloud: is allowed.'
        ),
        'OVERWRITE': (
            'no (default) refuses when an existing destination file differs; '
            'yes replaces differing files; replace also removes destination '
            'files the source lacks.'
        ),
        'GLOB': (
            'Comma-separated file-name patterns to move from a directory; '
            'other files stay at the source.'
        ),
        'EXCLUDE': (
            'Comma-separated names or patterns to leave behind at any depth. '
            'Adds to the defaults __pycache__, *.pyc, .DS_Store and '
            'script_snapshots; EXCLUDE: none switches the defaults off.'
        ),
        'DRY_RUN': 'With yes, plan and list the move without changing anything.',
        'CONFIRM': (
            'With yes, allow a move that changes more than 200 files or '
            'touches protected core paths.'
        ),
    },
    'internal_directives': [],
    'common_failures': [
        'The source does not exist.',
        'An existing destination file differs and OVERWRITE is no.',
        'A file is not UTF-8 text; binary moves are not supported yet.',
        'The move changes more than 200 files without CONFIRM: yes.',
        'The source and destination overlap, or a path escapes its root.',
    ],
    'safe_usage': [
        'Preview directory moves with DRY_RUN: yes first.',
        'Files skipped by filters stay at the source, so their directories remain.',
        'REVERT the run to put a moved tree back exactly.',
    ],
    'related_ops': [
        'COPY copies without removing the source.',
        'MAP inspects a source directory before moving it.',
        'DIFF and REVERT cover every file the move recorded.',
    ],
}


HINTS = {
    '_max_hints': 1,
    'destination exists': {
        'message': 'MOVE found differing files at the destination.',
        'why': 'MOVE protects existing files by default so replacing them is a decision, not a surprise.',
        'example': [
            'MOVE projects/app',
            'TO: icloud:projects/app',
            'OVERWRITE: yes',
            'DRY_RUN: yes',
        ],
        'next': [
            'Preview with DRY_RUN: yes to see every planned change.',
            'OVERWRITE: yes replaces differing files; OVERWRITE: replace also removes extras.',
        ],
        'priority': 100,
    },
    'utf-8': {
        'message': 'MOVE only transfers UTF-8 text files for now.',
        'why': 'Run recovery stores text, so a binary file could not be restored by REVERT.',
        'example': [
            'MOVE projects/app',
            'TO: icloud:projects/app',
            'EXCLUDE: *.png, *.wav',
        ],
        'next': [
            'Leave the named files behind with EXCLUDE, or move only text with GLOB.',
        ],
        'priority': 95,
    },
    'confirm: yes': {
        'message': 'This MOVE needs CONFIRM: yes.',
        'why': 'Large moves and protected core paths are deliberate decisions.',
        'example': [
            'MOVE projects/big',
            'TO: icloud:projects/big',
            'DRY_RUN: yes',
        ],
        'next': [
            'Preview with DRY_RUN: yes, then add CONFIRM: yes if it is intended.',
        ],
        'priority': 92,
    },
    'to': {
        'message': 'MOVE needs TO: destination/path.',
        'why': 'The source goes on the MOVE line and the destination goes in TO.',
        'example': [
            'MOVE scratch/old_name.py',
            'TO: scratch/new_name.py',
        ],
        'next': [
            'Add TO: with the destination path itself.',
        ],
        'priority': 90,
    },
    'source': {
        'message': 'MOVE needs an existing source file or directory.',
        'why': 'MOVE reads the source, writes it to the destination, then removes it.',
        'example': [
            'MOVE scratch/old_name.py',
            'TO: scratch/new_name.py',
        ],
        'next': [
            'Use MAP on the containing directory or SEARCH to confirm the source path.',
        ],
        'priority': 80,
    },
}


def validate(parsed_op):
    return validate_transfer('MOVE', parsed_op)


def execute(ctx, parsed_op, result):
    execute_transfer(ctx, parsed_op, result, 'MOVE')