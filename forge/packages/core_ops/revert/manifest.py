"""REVERT op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/revert
"""

MANIFEST = {
    'name': 'revert',
    'op': 'REVERT',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Restore project files to their pre-run state using a stored Forge run.',
    'risk': 'write',
    'domains': ['runs', 'recovery', 'files'],
}