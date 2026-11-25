"""DIFF op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/diff
"""

MANIFEST = {
    'name': 'diff',
    'op': 'DIFF',
    'kind': 'core-op',
    'version': '0.2.0',
    'summary': 'Review touched file changes compactly by default, with full line diff on request.',
    'risk': 'read-only',
    'domains': ['recovery', 'snapshots', 'inspection'],
}
