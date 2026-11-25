"""COPY op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/copy
"""

MANIFEST = {
    'name': 'copy',
    'version': '0.2.0',
    'op': 'COPY',
    'kind': 'core-op',
    'summary': 'COPY copies a file or directory tree, across roots, recording every file for REVERT.',
}