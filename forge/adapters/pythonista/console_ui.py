# -*- coding: utf-8 -*-
"""
Portable Forge live console renderer for Pythonista.

This is a host-side presentation adapter.

Portable Forge Core emits structured execution events. This module turns those
events into the old-Forge-inspired Pythonista console presentation without
changing Forge execution or the canonical return packet.
"""

import sys
import threading
import time

try:
    import console
except Exception:
    console = None


PORTABLE_FORGE_PYTHONISTA_LIVE_UI = (
    "portable-forge-pythonista-live-ui-v1"
)

WIDTH = 41
BAR_WIDTH = 22
TIMING_BAR_WIDTH = 17
# Pythonista's console cannot move the cursor, so every live update is a full
# clear-and-redraw. Keep them rare: at most one frame per second, and none at
# all for runs that finish within LIVE_START_DELAY.
LIVE_FRAME_INTERVAL = 1.0
LIVE_START_DELAY = 1.0
LIVE_RECENT_OPERATIONS = 8


HEX = {
    "accent": "#5AA9FF",
    "border": "#E91E63",
    "danger": "#FF5A5F",
    "muted": "#9FB4C9",
    "success": "#4CD964",
    "text": "#EEF6FF",
    "warning": "#FFD166",
    "orange": "#FF9F43",
    "cyan": "#5DEBFF",
}


def _hex_to_rgb(value):
    value = value.strip().lstrip("#")

    return tuple(
        int(
            value[i:i + 2],
            16,
        )
        / 255.0
        for i in (
            0,
            2,
            4,
        )
    )


PALETTE = {
    name: _hex_to_rgb(value)
    for name, value
    in HEX.items()
}


class ForgeConsoleUI(object):
    """
    Live execution renderer: a console display rebuilt at most once per second.

    Events only mark the display as changed; a timer thread redraws once per
    LIVE_FRAME_INTERVAL when something changed or an operation's clock is
    visibly running. Runs shorter than LIVE_START_DELAY are drawn once, at
    the end.

    The current stdout object is captured when the renderer is constructed.
    Forge RUN operations may temporarily redirect global sys.stdout while
    capturing child-script output. Holding the original stream keeps this
    progress display visible without contaminating RUN stdout.
    """

    def __init__(self):
        self.stream = sys.stdout

        self.started = False
        self.finished = False
        self.stamp = ""
        self.mode = "dev"
        self.total = 0

        self.operations = []
        self.timings = []
        self.active_operation = None

        self.applied = 0
        self.skipped = 0
        self.failed = 0

        self.run_status = ""
        self.run_elapsed = 0.0
        self.error_count = 0
        self.packet_bytes = 0

        self._render_lock = threading.RLock()
        self._timer_stop = threading.Event()
        self._timer_thread = None
        self._clock_start = None
        self._dirty = False

    def _flush(self):
        try:
            self.stream.flush()
        except Exception:
            pass

    def _colour(self, name="text"):
        if console is None:
            return

        try:
            console.set_color(
                *PALETTE.get(
                    name,
                    PALETTE["text"],
                )
            )
        except Exception:
            pass

    def _reset(self):
        self._colour(
            "text"
        )

    def _set_font(self):
        if console is None:
            return

        try:
            console.set_font(
                "Menlo",
                15,
            )
        except Exception:
            pass

    def _clear(self):
        if console is None:
            return

        try:
            console.clear()
        except Exception:
            pass

    def _write(
        self,
        text="",
        tone="text",
        end="\n",
    ):
        self._colour(
            tone
        )

        print(
            str(text),
            end=end,
            file=self.stream,
        )

        self._reset()
        self._flush()

    def _plain(
        self,
        text="",
        end="\n",
    ):
        print(
            str(text),
            end=end,
            file=self.stream,
        )

        self._flush()

    def _center(
        self,
        text,
        width=WIDTH,
    ):
        text = str(
            text
        )

        if len(text) >= width:
            return text

        return (
            " "
            * (
                (
                    width
                    - len(text)
                )
                // 2
            )
            + text
        )

    def _spaced(
        self,
        text,
    ):
        return " ".join(
            str(
                text
            ).upper()
        )

    def _seconds(
        self,
        value,
    ):
        try:
            value = float(
                value
            )
        except Exception:
            return "?"

        if value < 0.01:
            return "{:.3f}s".format(
                value
            )

        if value < 1:
            return "{:.2f}s".format(
                value
            )

        return "{:.1f}s".format(
            value
        )

    def _bytes(
        self,
        value,
    ):
        try:
            value = max(
                0,
                int(
                    value
                ),
            )
        except Exception:
            value = 0

        if value < 1024:
            return "{} B".format(
                value
            )

        if value < (
            1024
            * 1024
        ):
            return "{:.1f} KB".format(
                value
                / 1024.0
            )

        return "{:.1f} MB".format(
            value
            / (
                1024.0
                * 1024.0
            )
        )

    def _progress_bar(
        self,
        done,
        total,
        width=BAR_WIDTH,
    ):
        try:
            done = int(
                done or 0
            )
        except Exception:
            done = 0

        try:
            total = int(
                total or 0
            )
        except Exception:
            total = 0

        if total <= 0:
            filled = 0

        else:
            filled = int(
                round(
                    width
                    * float(done)
                    / float(total)
                )
            )

        filled = max(
            0,
            min(
                width,
                filled,
            ),
        )

        return (
            "█"
            * filled
            + "░"
            * (
                width
                - filled
            )
        )

    def _hero(self):
        self._write(
            "═" * WIDTH,
            "border",
        )

        self._write(
            self._center(
                self._spaced(
                    "FORGE"
                )
            ),
            "accent",
        )

        self._write(
            self._center(
                "{}  ·  LIVE EXECUTION".format(
                    str(
                        self.mode
                        or "dev"
                    ).upper()
                )
            ),
            "muted",
        )

        self._write(
            "═" * WIDTH,
            "border",
        )

        self._plain()

    def _ensure_started(self):
        if self.started:
            return

        self.started = True
        self._clock_start = time.monotonic()
        self._set_font()
        self._dirty = True

        # The clock must continue while a Forge operation blocks the caller.
        # Do not start a display thread outside Pythonista's console host.
        if console is not None and not self.finished:
            self._timer_thread = threading.Thread(
                target=self._timer_loop,
                name="ForgeConsoleTimer",
                daemon=True,
            )
            self._timer_thread.start()

    def _timer_loop(self):
        """Refresh the display between Forge's operation events."""
        if self._timer_stop.wait(LIVE_START_DELAY):
            return
        while True:
            with self._render_lock:
                if self.finished:
                    return
                # Redraw only when something changed or a clock is visibly ticking.
                if self._dirty or self.active_operation is not None:
                    try:
                        self._render_live()
                    except Exception:
                        # Presentation must not interfere with Forge execution.
                        self._timer_stop.set()
                        return
            if self._timer_stop.wait(LIVE_FRAME_INTERVAL):
                return

    def _render_live(self, show_all=False):
        """Rebuild the visible console from retained operation state.

        The frame is assembled first and written with one print per run of
        same-coloured lines, so it appears at once rather than line by line.
        """
        self._dirty = False
        lines = self._hero_lines() + self._live_lines(show_all)
        self._clear()
        self._set_font()
        self._emit(lines)

    def _hero_lines(self):
        return [
            ("border", "═" * WIDTH),
            ("accent", self._center(self._spaced("FORGE"))),
            ("muted", self._center("{}  ·  LIVE EXECUTION".format(
                str(self.mode or "dev").upper()))),
            ("border", "═" * WIDTH),
            ("text", ""),
        ]

    def _live_lines(self, show_all):
        """(tone, text) lines for completed, active and progress sections."""
        lines = []
        completed = len(self.operations)
        first = 0 if show_all else max(0, completed - LIVE_RECENT_OPERATIONS)

        if completed:
            if first:
                lines.append(("muted", "  {} earlier operation(s)".format(first)))
            lines.append(("muted", "Completed"))
            for position in range(first, completed):
                op, target, status = self.operations[position]
                seconds = self.timings[position][2]
                lines.append((self._status_tone(status), "  {} {:02d}/{:02d}  {:<8}  {}".format(
                    "✓" if status == "APPLIED" else "•",
                    position + 1, self.total, op, self._seconds(seconds))))
                lines.append(("text", "      " + target))
            lines.append(("text", ""))

        if self.active_operation is not None:
            active = self.active_operation
            elapsed = time.monotonic() - active["started_at"]
            # One spinner step per frame, i.e. per second.
            spinner = "◐◓◑◒"[int(elapsed) % 4]
            lines.append(("muted", "Active operation"))
            lines.append(("accent", "  {} {:02d}/{:02d}  {:<8}  {}s".format(
                spinner, active["index"], self.total, active["op"], int(elapsed))))
            lines.append(("text", "      " + active["target"]))
        elif self.finished:
            lines.append(("muted", "Execution finished"))
        else:
            lines.append(("muted", "Waiting for next operation"))

        lines.append(("text", ""))
        lines.append(("accent", "  {}  {}/{}".format(
            self._progress_bar(completed, self.total), completed, self.total)))
        lines.append(("cyan", "  Run timer: {}s".format(
            int(time.monotonic() - self._clock_start))))
        return lines

    def _emit(self, lines):
        """Write (tone, text) lines with one print per run of the same tone."""
        run_tone, run = None, []
        for tone, text in lines + [(None, None)]:
            if tone != run_tone and run:
                self._colour(run_tone)
                print("\n".join(run), file=self.stream)
                run = []
            run_tone = tone
            if text is not None:
                run.append(text)
        self._reset()
        self._flush()

    def _status_tone(
        self,
        status,
    ):
        status = str(
            status
            or ""
        ).upper()

        if status == "APPLIED":
            return "success"

        if "SKIP" in status:
            return "warning"

        if "FAIL" in status:
            return "danger"

        return "muted"

    def _status_word(
        self,
        status,
    ):
        status = str(
            status
            or ""
        ).upper()

        if status == "APPLIED":
            return "applied"

        if "SKIP" in status:
            return "skipped"

        if status:
            return status.lower()

        return "unknown"

    def _record_status(
        self,
        status,
    ):
        status = str(
            status
            or ""
        ).upper()

        if status == "APPLIED":
            self.applied += 1
            return

        if "SKIP" in status:
            self.skipped += 1
            return

        self.failed += 1

    def _live_start(self, event):
        self._ensure_started()
        self.total = event.get("total") or self.total or 0
        self.active_operation = {
            "index": int(event.get("index") or 0),
            "op": str(event.get("op") or "?").upper(),
            "target": str(event.get("target") or ""),
            "started_at": time.monotonic(),
        }
        self._dirty = True

    def _live_finish(self, event):
        self._ensure_started()
        self.total = event.get("total") or self.total or 0

        op = str(event.get("op") or "?").upper()
        target = str(event.get("target") or "")
        status = str(event.get("status") or "").upper()
        try:
            elapsed = float(event.get("elapsed_seconds") or 0.0)
        except (TypeError, ValueError):
            elapsed = 0.0

        self.operations.append((op, target, status))
        self.timings.append((op, target, elapsed))
        self._record_status(status)
        self.active_operation = None
        self._dirty = True

    def _outcome_graph(self):
        values = [
            (
                "applied",
                self.applied,
                "success",
            ),
            (
                "skipped",
                self.skipped,
                "warning",
            ),
            (
                "failed",
                self.failed,
                "danger",
            ),
        ]

        largest = max(
            [
                value
                for _label, value, _tone
                in values
            ]
            + [1]
        )

        self._write(
            "Outcome",
            "muted",
        )

        for label, value, tone in values:
            if value:
                filled = max(
                    1,
                    int(
                        round(
                            14
                            * float(value)
                            / float(largest)
                        )
                    ),
                )

            else:
                filled = 0

            bar = (
                "█"
                * filled
                + "░"
                * (
                    14
                    - filled
                )
            )

            self._colour(
                tone
            )

            print(
                "  {:<8} ".format(
                    label
                ),
                end="",
                file=self.stream,
            )

            print(
                bar,
                end="",
                file=self.stream,
            )

            self._reset()

            print(
                "  {}".format(
                    value
                ),
                file=self.stream,
            )

            self._flush()

    def _timing_graph(self):
        if not self.timings:
            return

        self._plain()

        self._write(
            "Operation time",
            "muted",
        )

        ordered = sorted(
            self.timings,
            key=lambda row: row[2],
            reverse=True,
        )

        longest = max(
            row[2]
            for row
            in ordered
        )

        for op, target, elapsed in ordered:
            if longest <= 0:
                length = 1

            else:
                length = max(
                    1,
                    int(
                        round(
                            TIMING_BAR_WIDTH
                            * elapsed
                            / longest
                        )
                    ),
                )

            self._colour(
                "accent"
            )

            print(
                "  {:<8} ".format(
                    str(
                        op
                    )[:8]
                ),
                end="",
                file=self.stream,
            )

            print(
                "█" * length,
                end="",
                file=self.stream,
            )

            self._reset()

            print(
                " "
                * (
                    TIMING_BAR_WIDTH
                    - length
                ),
                end="",
                file=self.stream,
            )

            print(
                "  {:>6}".format(
                    self._seconds(
                        elapsed
                    )
                ),
                file=self.stream,
            )

            self._flush()

    def _clean_summary(self):
        self._write(
            self._center(
                self._spaced(
                    "RUN CLEAN"
                )
            ),
            "success",
        )

        self._write(
            self._center(
                "{} operations · {} total".format(
                    len(
                        self.operations
                    ),
                    self._seconds(
                        self.run_elapsed
                    ),
                )
            ),
            "muted",
        )


        self._write(
            self._center(
                "Packet · {}".format(
                    self._bytes(
                        self.packet_bytes
                    )
                )
            ),
            "muted",
        )

        self._plain()

        self._write(
            "Run clean. {} operations applied with".format(
                self.applied
            ),
            "text",
        )

        self._write(
            "no visible errors.",
            "text",
        )

    def _failed_summary(self):
        self._write(
            self._center(
                self._spaced(
                    "RUN FAILED"
                )
            ),
            "danger",
        )

        self._write(
            self._center(
                "{} operations · {} total".format(
                    len(
                        self.operations
                    ),
                    self._seconds(
                        self.run_elapsed
                    ),
                )
            ),
            "muted",
        )


        self._write(
            self._center(
                "Packet · {}".format(
                    self._bytes(
                        self.packet_bytes
                    )
                )
            ),
            "muted",
        )

        self._plain()

        self._write(
            "Run failed. {} applied · {} skipped ·".format(
                self.applied,
                self.skipped,
            ),
            "text",
        )

        self._write(
            "{} failed · {} error(s) reported.".format(
                self.failed,
                self.error_count,
            ),
            "text",
        )

    def _completion(
        self,
        event,
    ):
        if self.finished:
            return

        self._ensure_started()
        self.finished = True
        self._timer_stop.set()
        self.active_operation = None
        self._render_live(show_all=True)

        self.run_status = str(
            event.get(
                "status"
            )
            or ""
        ).upper()

        try:
            self.run_elapsed = float(
                event.get(
                    "elapsed_seconds"
                )
                or 0.0
            )
        except Exception:
            self.run_elapsed = 0.0

        try:
            self.error_count = int(
                event.get(
                    "error_count"
                )
                or 0
            )
        except Exception:
            self.error_count = 0


        try:
            self.packet_bytes = int(
                event.get(
                    "packet_bytes"
                )
                or 0
            )
        except Exception:
            self.packet_bytes = 0

        self._write(
            "═" * WIDTH,
            "border",
        )

        self._plain()

        if (
            self.run_status
            == "APPLIED"
            and self.failed == 0
        ):
            self._clean_summary()

        else:
            self._failed_summary()

        self._plain()

        self._outcome_graph()
        self._timing_graph()

        self._plain()

        if (
            self.run_status
            == "APPLIED"
            and self.failed == 0
        ):
            self._write(
                self._center(
                    "🧠  Summary enough"
                ),
                "success",
            )

        else:
            self._write(
                self._center(
                    "⚠  Inspect return packet"
                ),
                "warning",
            )

        self._plain()

        self._write(
            "─" * WIDTH,
            "border",
        )

    def print_clipboard_status(
        self,
        ok=True,
    ):
        if ok:
            self._write(
                "✓ Return packet copied to clipboard",
                "success",
            )

        else:
            self._write(
                "✕ Return packet was not copied",
                "danger",
            )

    def __call__(self, event):
        if not isinstance(event, dict):
            return

        with self._render_lock:
            name = str(event.get("event") or "")

            if name == "run_started":
                self.stamp = str(event.get("stamp") or "")
                self.mode = str(event.get("mode") or "dev")
                self._ensure_started()
            elif name == "operation_started":
                self._live_start(event)
            elif name == "operation_finished":
                self._live_finish(event)
            elif name == "run_finished":
                self._completion(event)