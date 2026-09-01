# -*- coding: utf-8 -*-
"""
Portable Forge live console renderer for Pythonista.

This is a host-side presentation adapter.

Portable Forge Core emits structured execution events. This module turns those
events into the old-Forge-inspired Pythonista console presentation without
changing Forge execution or the canonical return packet.
"""

import sys

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
    Append-only live execution renderer.

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

        self.applied = 0
        self.skipped = 0
        self.failed = 0

        self.run_status = ""
        self.run_elapsed = 0.0
        self.error_count = 0

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

        self._clear()
        self._set_font()
        self._hero()

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

    def _live_start(
        self,
        event,
    ):
        self._ensure_started()

        index = event.get(
            "index"
        ) or 0

        total = event.get(
            "total"
        ) or self.total or 0

        self.total = total

        op = str(
            event.get(
                "op"
            )
            or "?"
        ).upper()

        target = str(
            event.get(
                "target"
            )
            or ""
        )

        self._colour(
            "accent"
        )

        print(
            "● {:02d}/{:02d}  {:<8}".format(
                int(
                    index
                ),
                int(
                    total
                ),
                op,
            ),
            file=self.stream,
        )

        self._reset()
        self._flush()

        self._write(
            "  "
            + target,
            "text",
        )

    def _live_finish(
        self,
        event,
    ):
        self._ensure_started()

        index = event.get(
            "index"
        ) or 0

        total = event.get(
            "total"
        ) or self.total or 0

        self.total = total

        op = str(
            event.get(
                "op"
            )
            or "?"
        ).upper()

        target = str(
            event.get(
                "target"
            )
            or ""
        )

        status = str(
            event.get(
                "status"
            )
            or ""
        ).upper()

        try:
            elapsed = float(
                event.get(
                    "elapsed_seconds"
                )
                or 0.0
            )
        except Exception:
            elapsed = 0.0

        self.operations.append(
            (
                op,
                target,
                status,
            )
        )

        self.timings.append(
            (
                op,
                target,
                elapsed,
            )
        )

        self._record_status(
            status
        )

        word = self._status_word(
            status
        )

        tone = self._status_tone(
            status
        )

        duration = self._seconds(
            elapsed
        )

        label = (
            "  ✓ "
            + word
            if status == "APPLIED"
            else "  • "
            + word
        )

        self._colour(
            tone
        )

        print(
            label,
            end="",
            file=self.stream,
        )

        self._reset()

        padding = max(
            1,
            WIDTH
            - len(label)
            - len(duration),
        )

        print(
            " " * padding
            + duration,
            file=self.stream,
        )

        self._flush()

        self._colour(
            "accent"
        )

        print(
            "  "
            + self._progress_bar(
                index,
                total,
            ),
            end="",
            file=self.stream,
        )

        self._reset()

        print(
            "  {}/{}".format(
                index,
                total,
            ),
            file=self.stream,
        )

        self._flush()
        self._plain()

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

        self.finished = True
        self._ensure_started()

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

    def __call__(
        self,
        event,
    ):
        if not isinstance(
            event,
            dict,
        ):
            return

        name = str(
            event.get(
                "event"
            )
            or ""
        )

        if name == "run_started":
            self.stamp = str(
                event.get(
                    "stamp"
                )
                or ""
            )

            self.mode = str(
                event.get(
                    "mode"
                )
                or "dev"
            )

            self._ensure_started()
            return

        if name == "operation_started":
            self._live_start(
                event
            )
            return

        if name == "operation_finished":
            self._live_finish(
                event
            )
            return

        if name == "run_finished":
            self._completion(
                event
            )