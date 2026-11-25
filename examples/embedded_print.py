"""Smallest useful example of embedding Portable Forge.

Role: run · Part of: forge/examples · Entry
"""

import os

import forge


PROJECT_ROOT = os.getcwd()

BUNDLE = """MAP .
DEPTH: 2

FORGE ops
"""


run = forge.run_text(
    BUNDLE,
    project_root=PROJECT_ROOT,
)

print(
    forge.render_standard(
        run
    )
)