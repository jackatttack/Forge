"""Behaviour checks for Pythonista's live Forge console renderer."""

import io
import sys
import time
import unittest
from unittest import mock

from forge.adapters.pythonista import console_ui


class FakeConsole:
    def __init__(self, output):
        self.output = output
        self.clear_count = 0
        self.last_clear_offset = 0

    def clear(self):
        self.clear_count += 1
        self.last_clear_offset = len(self.output.getvalue())

    def set_color(self, *components):
        pass

    def set_font(self, *settings):
        pass

    def latest_frame(self):
        return self.output.getvalue()[self.last_clear_offset:]


class ConsoleAnimationTests(unittest.TestCase):
    def test_timer_refreshes_without_contaminating_run_output(self):
        output = io.StringIO()
        captured_child_output = io.StringIO()
        fake_console = FakeConsole(output)

        # Speed the clock up for the test; the shipped interval is one second.
        with mock.patch.object(console_ui, "LIVE_FRAME_INTERVAL", 0.05), \
                mock.patch.object(console_ui, "LIVE_START_DELAY", 0.05), \
                mock.patch.object(console_ui, "console", fake_console):
            with mock.patch.object(sys, "stdout", output):
                renderer = console_ui.ForgeConsoleUI()
                try:
                    renderer({
                        "event": "run_started",
                        "stamp": "DEMO",
                        "mode": "dev",
                    })
                    renderer({
                        "event": "operation_started",
                        "index": 1,
                        "total": 11,
                        "op": "RUN",
                        "target": "slow_script.py",
                    })

                    initial_redraws = fake_console.clear_count
                    with mock.patch.object(
                        sys, "stdout", captured_child_output
                    ):
                        time.sleep(0.32)

                    self.assertGreater(
                        fake_console.clear_count, initial_redraws
                    )
                    self.assertEqual(
                        captured_child_output.getvalue(), ""
                    )
                    self.assertIn(
                        "slow_script.py", fake_console.latest_frame()
                    )
                    self.assertIn(
                        "Run timer:", fake_console.latest_frame()
                    )

                    renderer({
                        "event": "operation_finished",
                        "index": 1,
                        "total": 11,
                        "op": "RUN",
                        "target": "slow_script.py",
                        "status": "APPLIED",
                        "elapsed_seconds": 0.32,
                    })

                    for index in range(2, 12):
                        target = "file_{:02d}.py".format(index)
                        renderer({
                            "event": "operation_started",
                            "index": index,
                            "total": 11,
                            "op": "READ",
                            "target": target,
                        })
                        renderer({
                            "event": "operation_finished",
                            "index": index,
                            "total": 11,
                            "op": "READ",
                            "target": target,
                            "status": "APPLIED",
                            "elapsed_seconds": 0.01,
                        })

                    time.sleep(0.15)  # let one coalesced frame render
                    self.assertIn(
                        "earlier operation(s)",
                        fake_console.latest_frame(),
                    )
                    self.assertNotIn(
                        "slow_script.py",
                        fake_console.latest_frame(),
                    )

                    renderer({
                        "event": "run_finished",
                        "status": "APPLIED",
                        "elapsed_seconds": 0.5,
                        "error_count": 0,
                        "packet_bytes": 42,
                    })
                    self.assertIn(
                        "slow_script.py",
                        fake_console.latest_frame(),
                    )
                    self.assertIn(
                        "Run clean. 11 operations applied",
                        fake_console.latest_frame(),
                    )

                    final_redraws = fake_console.clear_count
                    renderer._timer_thread.join(timeout=0.5)
                    self.assertFalse(renderer._timer_thread.is_alive())
                    self.assertEqual(
                        fake_console.clear_count, final_redraws
                    )
                finally:
                    renderer._timer_stop.set()


    def test_fast_runs_render_once_at_the_end(self):
        """Quick bundles never animate: no live frames, one final screen."""
        output = io.StringIO()
        fake_console = FakeConsole(output)
        with mock.patch.object(console_ui, "console", fake_console):
            with mock.patch.object(sys, "stdout", output):
                renderer = console_ui.ForgeConsoleUI()
                try:
                    renderer({"event": "run_started", "stamp": "FAST", "mode": "dev"})
                    for index in range(1, 6):
                        event = {"index": index, "total": 5, "op": "READ",
                                 "target": "file_{}.py".format(index)}
                        renderer(dict(event, event="operation_started"))
                        renderer(dict(event, event="operation_finished",
                                      status="APPLIED", elapsed_seconds=0.01))
                    self.assertEqual(fake_console.clear_count, 0)
                    renderer({"event": "run_finished", "status": "APPLIED",
                              "elapsed_seconds": 0.05, "error_count": 0,
                              "packet_bytes": 42})
                    self.assertEqual(fake_console.clear_count, 1)
                    self.assertIn("Run clean. 5 operations applied",
                                  fake_console.latest_frame())
                finally:
                    renderer._timer_stop.set()


if __name__ == "__main__":
    unittest.main()