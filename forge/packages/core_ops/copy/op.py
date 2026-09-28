# -*- coding: utf-8 -*-
"""
COPY operation.

Copy one file or a whole directory tree, within a root or across named
roots. The shared engine in forge.core.file_transfer plans the complete
copy, refuses it before writing if anything is wrong, and records every
file it creates, replaces or removes so DIFF and REVERT cover the copy.

Contract:

    COPY source/path
    TO: destination/path
    OVERWRITE: no|yes|replace
    GLOB: *.py, *.md
    EXCLUDE: build, *.log
    DRY_RUN: yes
    CONFIRM: yes

The source is read, never changed.
"""

from forge.core.file_transfer import execute_transfer, validate_transfer


SPEC = {
    'name': 'COPY',
    'target_kind': 'file',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'TO', 'OVERWRITE', 'GLOB', 'EXCLUDE', 'DRY_RUN', 'CONFIRM',
    ]),
    'required_directives': set(['TO']),
}


HELP = {
    'summary': (
        'Copy a file or a whole directory, within a root or across named roots.'
    ),
    'brief': (
        'COPY source with TO: destination (the new path itself; icloud: ok) · '
        'OVERWRITE: no|yes|replace · GLOB/EXCLUDE filter directories · '
        'DRY_RUN: yes previews.'
    ),
    'minimal_example': [
        'COPY scratch/source.py',
        'TO: scratch/copy.py',
        '',
        'COPY projects/tilekit/tilekit',
        'TO: icloud:projects/game/tilekit',
        'OVERWRITE: replace',
        'DRY_RUN: yes',
    ],
    'directives': {
        'TO': (
            'Required destination: the new file or directory path itself, '
            'never a folder to copy into. A root prefix such as icloud: is allowed.'
        ),
        'OVERWRITE': (
            'no (default) refuses when an existing destination file differs; '
            'yes replaces differing files; replace also removes destination '
            'files the source lacks.'
        ),
        'GLOB': (
            'Comma-separated file-name patterns to keep in a directory copy, '
            'for example *.py, *.md.'
        ),
        'EXCLUDE': (
            'Comma-separated names or patterns to skip at any depth. Adds to '
            'the defaults __pycache__, *.pyc, .DS_Store and script_snapshots; '
            'EXCLUDE: none switches the defaults off.'
        ),
        'DRY_RUN': 'With yes, plan and list the copy without writing anything.',
        'CONFIRM': (
            'With yes, allow a copy that changes more than 200 files or '
            'touches protected core paths.'
        ),
    },
    'internal_directives': [],
    'common_failures': [
        'The source does not exist.',
        'An existing destination file differs and OVERWRITE is no.',
        'A file is not UTF-8 text; binary copies are not supported yet.',
        'The copy changes more than 200 files without CONFIRM: yes.',
        'The source and destination overlap, or a path escapes its root.',
    ],
    'safe_usage': [
        'Check large or replacing copies with DRY_RUN: yes first.',
        'Use MOVE rather than COPY then DELETE when the source should go.',
        'Skip binary files with EXCLUDE until binary transfer exists.',
    ],
    'related_ops': [
        'MOVE copies, verifies, then removes the source in one recorded step.',
        'MAP inspects a source directory before copying it.',
        'DIFF and REVERT cover every file the copy recorded.',
    ],
}


HINTS = {
    '_max_hints': 1,
    'destination exists': {
        'message': 'COPY found differing files at the destination.',
        'why': 'COPY protects existing files by default so replacing them is a decision, not a surprise.',
        'example': [
            'COPY projects/app',
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
        'message': 'COPY only transfers UTF-8 text files for now.',
        'why': 'Run recovery stores text, so a binary file could not be restored by REVERT.',
        'example': [
            'COPY projects/app',
            'TO: icloud:projects/app',
            'EXCLUDE: *.png, *.wav',
        ],
        'next': [
            'Skip the named files with EXCLUDE, or keep only text with GLOB.',
        ],
        'priority': 95,
    },
    'confirm: yes': {
        'message': 'This COPY needs CONFIRM: yes.',
        'why': 'Large copies and protected core paths are deliberate decisions.',
        'example': [
            'COPY projects/big',
            'TO: icloud:projects/big',
            'DRY_RUN: yes',
        ],
        'next': [
            'Preview with DRY_RUN: yes, then add CONFIRM: yes if it is intended.',
        ],
        'priority': 92,
    },
    'to': {
        'message': 'COPY needs TO: destination/path.',
        'why': 'The source goes on the COPY line and the destination goes in TO.',
        'example': [
            'COPY scratch/source.py',
            'TO: scratch/source_copy.py',
        ],
        'next': [
            'Add TO: with the destination path itself.',
        ],
        'priority': 90,
    },
    'source': {
        'message': 'COPY needs an existing source file or directory.',
        'why': 'COPY reads the source and writes it to the destination.',
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


def validate(parsed_op):
    return validate_transfer('COPY', parsed_op)


def execute(ctx, parsed_op, result):
    execute_transfer(ctx, parsed_op, result, 'COPY')