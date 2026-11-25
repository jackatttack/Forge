"""DELETE op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/delete
"""

MANIFEST = {
    'name': 'delete',
    'op': 'DELETE',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Delete files, explicit line ranges, and exact text blocks.',
    'risk': 'mutating',
    'domains': ['filesystem', 'source', 'text', 'recovery'],
}
