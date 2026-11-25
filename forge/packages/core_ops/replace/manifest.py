"""REPLACE op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/replace
"""

MANIFEST = {
    'name': 'replace',
    'op': 'REPLACE',
    'kind': 'core-op',
    'version': '0.2.0',
    'summary': 'Replace an AST target or explicit file line range with recovery metadata.',
    'risk': 'mutating',
    'domains': ['source', 'ast', 'text', 'recovery'],
}
