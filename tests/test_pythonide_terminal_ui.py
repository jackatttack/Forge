# -*- coding: utf-8 -*-
"""Regression tests for the PythonIDE terminal adapter."""

import importlib.util
import os
import unittest


ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

UI_PATH = os.path.join(
    ROOT,
    'adapters',
    'pythonide',
    'forge_live_ui.py',
)

ENTRY_PATH = os.path.join(
    ROOT,
    'adapters',
    'pythonide',
    'forge-entry.py',
)


def load_ui_module():
    spec = importlib.util.spec_from_file_location(
        'forge_pythonide_terminal_ui_under_test',
        UI_PATH,
    )
    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(
        module
    )
    return module


class PythonIDETerminalUITests(unittest.TestCase):
    def setUp(self):
        self.module = load_ui_module()
        self.ui = self.module.ForgeLiveUI()

    def test_renderer_uses_single_line_animation_contract(self):
        with open(
            UI_PATH,
            'r',
            encoding='utf-8',
        ) as handle:
            source = handle.read()

        self.assertIn(
            'SPINNER_FRAMES',
            source,
        )
        self.assertIn(
            '\\r\\x1b[2K',
            source,
        )
        self.assertNotIn(
            'from rich.live import Live',
            source,
        )

    def test_status_words_match_public_terminal_language(self):
        self.assertEqual(
            self.ui._status_word('APPLIED'),
            'applied',
        )
        self.assertEqual(
            self.ui._status_word('SKIPPED_ALREADY_PRESENT'),
            'skipped',
        )
        self.assertEqual(
            self.ui._status_word('FAILED_RUNTIME'),
            'failed',
        )

    def test_progress_bar_contains_counter_and_is_bounded(self):
        bar = self.ui._progress_bar(
            3,
            5,
        )

        self.assertIn(
            '3/5',
            bar,
        )
        self.assertLessEqual(
            self.ui._width(),
            self.ui.MAX_WIDTH,
        )
        self.assertGreaterEqual(
            self.ui._width(),
            30,
        )

    def test_launcher_hides_bridge_preamble_by_default(self):
        with open(
            ENTRY_PATH,
            'r',
            encoding='utf-8',
        ) as handle:
            source = handle.read()

        self.assertIn(
            'SHOW_BRIDGE_PREAMBLE = False',
            source,
        )


if __name__ == '__main__':
    unittest.main()
