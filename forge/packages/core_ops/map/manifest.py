"""MAP op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/map
"""

MANIFEST = {
    'name': 'map',
    'op': 'MAP',
    'kind': 'core-op',
    'version': '0.3.0',
    'summary': 'Map source structure with smart defaults for directories, large files, imports, and READ targets.',
    'risk': 'read-only',
    'domains': ['inspection', 'structure', 'source', 'navigation', 'context'],
}