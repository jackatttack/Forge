"""FORGE op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/forge
"""

MANIFEST = {
    'name': 'forge',
    'op': 'FORGE',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Inspect Forge itself: operations, help, workflow docs, health, configuration, and stored runs.',
    'risk': 'read-only',
    'domains': ['forge', 'registry', 'help', 'audit', 'runs', 'configuration'],
}