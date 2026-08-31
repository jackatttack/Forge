# -*- coding: utf-8 -*-
"""
Educational terminal wrapper.

For normal terminal use, prefer the built-in command:

    python -m forge bundle.txt
"""

import os
import sys

import forge


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            'Usage: python terminal_file.py BUNDLE_FILE [PROJECT_ROOT]'
        )

    bundle_path = os.path.abspath(
        sys.argv[1]
    )

    project_root = os.path.abspath(
        sys.argv[2]
        if len(sys.argv) > 2
        else os.getcwd()
    )

    with open(
        bundle_path,
        'r',
        encoding='utf-8',
    ) as handle:
        bundle = handle.read()

    run = forge.run_text(
        bundle,
        project_root=project_root,
    )

    print(
        forge.render_standard(
            run
        ),
        end='',
    )


if __name__ == '__main__':
    main()