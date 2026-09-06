# -*- coding: utf-8 -*-
"""Regression tests for the Pythonista launcher clipboard boundary."""

import ast
import os


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

LAUNCHER_PATH = os.path.join(
    ROOT,
    'adapters',
    'pythonista',
    'Forge.py',
)


def load_clipboard_safe_text():
    """
    Compile only the clipboard sanitizer from the checkout launcher source.

    Forge RUN is in-process, so importing the launcher directly would also
    import Pythonista and Forge runtime modules. AST extraction keeps this test
    isolated from the live host.
    """
    with open(
        LAUNCHER_PATH,
        'r',
        encoding='utf-8',
    ) as handle:
        tree = ast.parse(
            handle.read(),
            filename=LAUNCHER_PATH,
        )

    function = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == '_clipboard_safe_text'
        )
    )

    namespace = {}

    exec(
        compile(
            ast.Module(
                body=[
                    function,
                ],
                type_ignores=[],
            ),
            LAUNCHER_PATH,
            'exec',
        ),
        namespace,
    )

    return namespace[
        '_clipboard_safe_text'
    ]


clipboard_safe_text = load_clipboard_safe_text()


def test_literal_nul_is_escaped():
    assert clipboard_safe_text(
        'before\x00after'
    ) == r'before\x00after'


def test_normal_packet_text_is_unchanged():
    assert clipboard_safe_text(
        'normal packet\n'
    ) == 'normal packet\n'


def test_multiple_nuls_are_all_escaped():
    assert clipboard_safe_text(
        '\x00a\x00'
    ) == r'\x00a\x00'


def main():
    test_literal_nul_is_escaped()
    test_normal_packet_text_is_unchanged()
    test_multiple_nuls_are_all_escaped()

    print(
        'PYTHONISTA LAUNCHER SAFETY PASS'
    )


if __name__ == '__main__':
    main()