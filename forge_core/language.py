# -*- coding: utf-8 -*-
"""
Forge Next public language definition.

Installed operations and public language are deliberately different concepts.

PUBLIC_OPS is the small everyday protocol an AI/human pair should normally
need to think about.

Other installed operations are optional powers. They may remain callable when
deliberately requested, but they are not part of the default language surface.

Removed legacy verbs are not aliases. Once their packages are deleted they
should stop parsing entirely.
"""

PUBLIC_OPS = (
    'FORGE',
    'MAP',
    'READ',
    'SEARCH',
    'WRITE',
    'REPLACE',
    'INSERT',
    'DELETE',
    'COPY',
    'RUN',
    'DIFF',
    'REVERT',
    'BRANCH',
    'URL',
    'ALIAS',
)

EXTENSION_OPS = (
    'CLIPBOARD',
    'EDITOR',
    'GIT',
    'MEMORY',
    'MOVE',
    'PACK',
    'PIP',
    'STRAVA',
    'SURFACE',
    'SYNC_EXPORT',
    'TRAINING',
)

REMOVED_OPS = {
    'CREATE_FILE': 'WRITE',
    'REPLACE_FILE': 'WRITE',
    'RUN_FILE': 'RUN',
    'REVERT_RUN': 'REVERT',
    'PREVIEW': 'READ',
    'LIST_TARGETS': 'READ or MAP',
    'LIST_FILES': 'MAP',
    'HELP': 'FORGE help',
    'LIST_OPS': 'FORGE ops',
    'AUDIT': 'FORGE audit',
    'RUNS': 'FORGE runs',
}


def public_ops():
    return list(PUBLIC_OPS)


def classify_op(name):
    name = str(name or '').strip().upper()

    if name in PUBLIC_OPS:
        return 'public'

    if name in EXTENSION_OPS:
        return 'extension'

    if name in REMOVED_OPS:
        return 'removed'

    return 'installed'


def replacement_for(name):
    return REMOVED_OPS.get(
        str(name or '').strip().upper(),
        '',
    )