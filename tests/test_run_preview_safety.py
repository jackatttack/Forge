# -*- coding: utf-8 -*-
"""Regression tests for bounded stored-run inspection output."""

import ast
import os


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

OP_PATH = os.path.join(
    ROOT,
    'forge',
    'packages',
    'core_ops',
    'forge',
    'op.py',
)


def load_preview_api():
    """
    Compile only the preview limit and helper from the checkout source.

    Forge RUN is in-process, so importing another forge.* tree can interfere
    with the live host. AST extraction keeps this regression test isolated.
    """
    with open(
        OP_PATH,
        'r',
        encoding='utf-8',
    ) as handle:
        tree = ast.parse(
            handle.read(),
            filename=OP_PATH,
        )

    wanted = []

    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == 'MAX_RUN_PREVIEW_BYTES'
                for target in node.targets
            )
        ):
            wanted.append(
                node
            )

        elif (
            isinstance(node, ast.FunctionDef)
            and node.name == '_bounded_run_preview'
        ):
            wanted.append(
                node
            )

    namespace = {}

    exec(
        compile(
            ast.Module(
                body=wanted,
                type_ignores=[],
            ),
            OP_PATH,
            'exec',
        ),
        namespace,
    )

    return (
        namespace['MAX_RUN_PREVIEW_BYTES'],
        namespace['_bounded_run_preview'],
    )


MAX_RUN_PREVIEW_BYTES, bounded_run_preview = load_preview_api()


def test_small_artifact_is_unchanged():
    assert bounded_run_preview(
        'hello\n'
    ) == 'hello'


def test_large_artifact_is_truncated_by_bytes():
    text = 'x' * (
        MAX_RUN_PREVIEW_BYTES
        + 4096
    )

    preview = bounded_run_preview(
        text
    )

    assert '[TRUNCATED - ' in preview
    assert (
        'first %d bytes shown'
        % MAX_RUN_PREVIEW_BYTES
    ) in preview

    assert len(
        preview.encode(
            'utf-8'
        )
    ) < len(
        text.encode(
            'utf-8'
        )
    )


def test_truncation_never_emits_broken_utf8():
    text = 'é' * (
        MAX_RUN_PREVIEW_BYTES
    )

    preview = bounded_run_preview(
        text
    )

    preview.encode(
        'utf-8'
    )

    assert '[TRUNCATED - ' in preview


def test_runs_paths_use_bounded_preview():
    with open(
        OP_PATH,
        'r',
        encoding='utf-8',
    ) as handle:
        tree = ast.parse(
            handle.read(),
            filename=OP_PATH,
        )

    runs_function = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == '_runs'
        )
    )

    calls = [
        node
        for node in ast.walk(
            runs_function
        )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == '_bounded_run_preview'
        )
    ]

    assert len(calls) >= 2


def main():
    test_small_artifact_is_unchanged()
    test_large_artifact_is_truncated_by_bytes()
    test_truncation_never_emits_broken_utf8()
    test_runs_paths_use_bounded_preview()

    print(
        'RUN PREVIEW SAFETY PASS'
    )


if __name__ == '__main__':
    main()