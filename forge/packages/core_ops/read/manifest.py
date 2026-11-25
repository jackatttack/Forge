"""READ op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/read
"""

MANIFEST = {
    'name': 'read',
    'op': 'READ',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Read files, AST targets, anchored slices, and Python target lists.',
    'risk': 'read-only',
    'domains': ['inspection', 'source', 'ast'],
}
