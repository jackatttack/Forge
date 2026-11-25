"""ALIAS op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/alias
"""

MANIFEST = {
    'name': 'alias',
    'op': 'ALIAS',
    'kind': 'custom-op',
    'version': '0.2.0',
    'risk': 'local-workflow',
    'summary': 'Manage local Forge aliases and one-line command shortcuts.',
    'domains': ['forge', 'workflow', 'shortcuts', 'preparse'],
}