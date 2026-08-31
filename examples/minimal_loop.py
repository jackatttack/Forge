# -*- coding: utf-8 -*-
"""
Smallest useful Forge host loop.

Replace get_bundle_text() and set_result_text() with whatever makes sense
for the environment.
"""

import os

import forge


PROJECT_ROOT = os.getcwd()


def get_bundle_text():
    return """MAP .
DEPTH: 2

FORGE ops
"""


def set_result_text(text):
    print(
        text,
        end='',
    )


def main():
    bundle = get_bundle_text()

    run = forge.run_text(
        bundle,
        project_root=PROJECT_ROOT,
    )

    result = forge.render_standard(
        run
    )

    set_result_text(
        result
    )


if __name__ == '__main__':
    main()