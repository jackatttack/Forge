"""RUN op manifest: what Forge's registry needs to load it.

Role: contracts · Part of: forge/ops/run
"""

MANIFEST = {
    'name': 'run',
    'op': 'RUN',
    'kind': 'core-op',
    'version': '0.1.0',
    'summary': 'Execute a Python file under the project root and capture stdout/stderr.',
    'risk': 'execute',
    'domains': ['execution', 'testing', 'validation'],
}