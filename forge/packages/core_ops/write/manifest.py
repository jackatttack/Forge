"""WRITE op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/write
"""

MANIFEST = {
    'name': 'write',
    'op': 'WRITE',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Write complete file contents, creating new files or explicitly overwriting existing files.',
    'risk': 'write',
    'domains': ['files', 'patching', 'recovery'],
}