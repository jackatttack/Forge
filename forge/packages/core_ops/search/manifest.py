"""SEARCH op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/search
"""

MANIFEST = {
    'name': 'search',
    'op': 'SEARCH',
    'kind': 'core-op',
    'version': '0.3.0',
    'summary': 'Search project files by text or Python AST structure.',
    'risk': 'read-only',
    'domains': ['inspection', 'search', 'source'],
}
