# -*- coding: utf-8 -*-
# portable-forge-pythonide-live-ui-v3
"""
Portable Forge terminal renderer for PythonIDE.

PythonIDE supports colour, Unicode and single-line in-place redraw well, but its
terminal does not reliably support Rich multi-line Live repainting.

This renderer therefore deliberately uses:

    static append-only Forge rows
    +
    one animated carriage-return spinner line
    +
    one permanent completion summary

Forge's canonical return packet remains completely separate and plain text.
"""

import sys
import threading
import time


PALETTE = {
    "accent": "#5AA9FF",
    "border": "#E91E63",
    "danger": "#FF5A5F",
    "muted": "#9FB4C9",
    "success": "#4CD964",
    "text": "#EEF6FF",
    "warning": "#FFD166",
    "cyan": "#5DEBFF",
}


SPINNER_FRAMES = (
    "⠋",
    "⠙",
    "⠹",
    "⠸",
    "⠼",
    "⠴",
    "⠦",
    "⠧",
    "⠇",
    "⠏",
)


class ForgeLiveUI:
    MAX_TIMINGS = 6
    MAX_WIDTH = 70
    TIMING_BAR_WIDTH = 14
    OUTCOME_BAR_WIDTH = 14

    def __init__(self):
        self.available = False
        self.console = None
        self.stream = sys.stdout

        self.stamp = ""
        self.mode = ""

        self.total = 0
        self.completed = 0

        self.status = "STARTING"

        self.started_at = time.monotonic()
        self.run_elapsed = 0.0

        self.applied = 0
        self.skipped = 0
        self.failed = 0

        self.error_count = 0
        self.packet_bytes = 0

        self.timings = []

        self._started = False
        self._finished = False

        self._spinner_thread = None
        self._spinner_stop = None
        self._spinner_started = 0.0
        self._spinner_label = ""
        self._spinner_lock = threading.Lock()

        try:
            from rich.console import Console

            self.console = Console(
                file=self.stream,
                highlight=False,
            )

            self.available = True

        except Exception:
            self.console = None
            self.available = False

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(value):
        return str(
            value
            or ""
        ).replace(
            "\n",
            " ",
        ).strip()

    @staticmethod
    def _elapsed(value):
        try:
            value = float(
                value
                or 0.0
            )
        except Exception:
            return ""

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

    @staticmethod
    def _bytes(value):
        try:
            value = int(
                value
                or 0
            )
        except Exception:
            value = 0

        if value < 1024:
            return "{} B".format(
                value
            )

        if value < 1024 * 1024:
            return "{:.1f} KB".format(
                value / 1024.0
            )

        return "{:.1f} MB".format(
            value
            / float(
                1024 * 1024
            )
        )

    @staticmethod
    def _spaced(value):
        return " ".join(
            str(
                value
                or ""
            )
        )

    def _width(self):
        try:
            width = int(
                self.console.width
            )
        except Exception:
            width = 52

        return max(
            30,
            min(
                self.MAX_WIDTH,
                width - 2,
            ),
        )

    @classmethod
    def _shorten(
        cls,
        value,
        limit,
    ):
        text = cls._clean(
            value
        )

        if len(text) <= limit:
            return text

        if limit <= 5:
            return text[:limit]

        usable = limit - 1
        left = usable // 2
        right = usable - left

        return (
            text[:left]
            + "…"
            + text[-right:]
        )

    # ------------------------------------------------------------------
    # Rich output helpers
    # ------------------------------------------------------------------

    def _print(
        self,
        text="",
        tone="text",
        bold=False,
        justify=None,
    ):
        if self.console is None:
            print(
                text,
                file=self.stream,
            )
            return

        try:
            from rich.text import Text

            style = PALETTE.get(
                tone,
                PALETTE["text"],
            )

            if bold:
                style = (
                    "bold "
                    + style
                )

            value = Text(
                str(
                    text
                    or ""
                ),
                style=style,
            )

            if justify:
                value.justify = justify

            self.console.print(
                value,
                soft_wrap=False,
            )

        except Exception:
            print(
                text,
                file=self.stream,
            )

    def _print_text(self, text):
        if self.console is None:
            print(
                str(text),
                file=self.stream,
            )
            return

        try:
            self.console.print(
                text,
                soft_wrap=False,
            )
        except Exception:
            print(
                str(text),
                file=self.stream,
            )

    def _rule(
        self,
        char="═",
    ):
        self._print(
            char * self._width(),
            tone="border",
        )

    def _center(
        self,
        text,
        tone="text",
        bold=False,
    ):
        self._print(
            text,
            tone=tone,
            bold=bold,
            justify="center",
        )

    # ------------------------------------------------------------------
    # Single-line animation
    # ------------------------------------------------------------------

    def _clear_spinner_line(self):
        try:
            self.stream.write(
                "\r\x1b[2K"
            )
            self.stream.flush()
        except Exception:
            pass

    def _spinner_loop(self):
        frame_index = 0

        while (
            self._spinner_stop is not None
            and not self._spinner_stop.wait(
                0.08
            )
        ):
            elapsed = (
                time.monotonic()
                - self._spinner_started
            )

            frame = SPINNER_FRAMES[
                frame_index
                % len(
                    SPINNER_FRAMES
                )
            ]

            frame_index += 1

            label = self._shorten(
                self._spinner_label,
                max(
                    8,
                    self._width()
                    - 14,
                ),
            )

            line = (
                "  {} {}  {:>5.1f}s".format(
                    frame,
                    label,
                    elapsed,
                )
            )

            with self._spinner_lock:
                try:
                    self.stream.write(
                        "\r\x1b[2K"
                    )

                    self.stream.write(
                        line
                    )

                    self.stream.flush()

                except Exception:
                    return

    def _spinner_start(
        self,
        label,
    ):
        self._spinner_finish()

        self._spinner_label = self._clean(
            label
        )

        self._spinner_started = (
            time.monotonic()
        )

        self._spinner_stop = (
            threading.Event()
        )

        self._spinner_thread = (
            threading.Thread(
                target=self._spinner_loop,
                name="ForgePythonIDESpinner",
                daemon=True,
            )
        )

        self._spinner_thread.start()

    def _spinner_finish(self):
        stop = self._spinner_stop
        thread = self._spinner_thread

        self._spinner_stop = None
        self._spinner_thread = None

        if stop is not None:
            try:
                stop.set()
            except Exception:
                pass

        if (
            thread is not None
            and thread is not threading.current_thread()
        ):
            try:
                thread.join(
                    timeout=0.25
                )
            except Exception:
                pass

        with self._spinner_lock:
            self._clear_spinner_line()

    # ------------------------------------------------------------------
    # Hero
    # ------------------------------------------------------------------

    def _hero(self):
        self._rule()

        self._center(
            self._spaced(
                "FORGE"
            ),
            tone="accent",
            bold=True,
        )

        self._center(
            "{}  ·  LIVE EXECUTION".format(
                str(
                    self.mode
                    or "dev"
                ).upper()
            ),
            tone="muted",
        )

        self._rule()

        self._print()

    def _ensure_started(self):
        if self._started:
            return

        self._started = True
        self._hero()

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _status_word(
        self,
        status,
    ):
        status = self._clean(
            status
        ).upper()

        if status == "APPLIED":
            return "applied"

        if status.startswith(
            "SKIPPED"
        ):
            return "skipped"

        if status.startswith(
            "FAILED"
        ):
            return "failed"

        return (
            status.lower()
            or "finished"
        )

    def _status_tone(
        self,
        status,
    ):
        status = self._clean(
            status
        ).upper()

        if status == "APPLIED":
            return "success"

        if status.startswith(
            "SKIPPED"
        ):
            return "warning"

        if status.startswith(
            "FAILED"
        ):
            return "danger"

        return "accent"

    def _record_status(
        self,
        status,
    ):
        status = self._clean(
            status
        ).upper()

        if status == "APPLIED":
            self.applied += 1

        elif status.startswith(
            "SKIPPED"
        ):
            self.skipped += 1

        elif status.startswith(
            "FAILED"
        ):
            self.failed += 1

    # ------------------------------------------------------------------
    # Operation presentation
    # ------------------------------------------------------------------

    def _operation_start(
        self,
        event,
    ):
        self._ensure_started()

        try:
            index = int(
                event.get(
                    "index"
                )
                or 0
            )
        except Exception:
            index = 0

        try:
            total = int(
                event.get(
                    "total"
                )
                or self.total
                or 0
            )
        except Exception:
            total = 0

        self.total = total

        op = self._clean(
            event.get(
                "op"
            )
        ).upper()

        target = self._shorten(
            event.get(
                "target"
            ),
            max(
                8,
                self._width()
                - 2,
            ),
        )

        self._print(
            "● {:02d}/{:02d}  {:<8}".format(
                index,
                total,
                op[:8],
            ),
            tone="accent",
            bold=True,
        )

        if target:
            self._print(
                "  " + target,
                tone="text",
            )

        self._spinner_start(
            op
        )

    def _progress_bar(
        self,
        index,
        total,
    ):
        try:
            index = int(
                index
                or 0
            )
        except Exception:
            index = 0

        try:
            total = int(
                total
                or 0
            )
        except Exception:
            total = 0

        counter = "{}/{}".format(
            index,
            total,
        )

        width = max(
            10,
            self._width()
            - len(counter)
            - 6,
        )

        if total <= 0:
            filled = 0

        else:
            ratio = max(
                0.0,
                min(
                    1.0,
                    float(index)
                    / float(total),
                ),
            )

            filled = int(
                round(
                    width
                    * ratio
                )
            )

        return (
            "  "
            + "█" * filled
            + "░" * (
                width
                - filled
            )
            + "  "
            + counter
        )

    def _operation_finish(
        self,
        event,
    ):
        self._spinner_finish()

        try:
            index = int(
                event.get(
                    "index"
                )
                or 0
            )
        except Exception:
            index = 0

        try:
            total = int(
                event.get(
                    "total"
                )
                or self.total
                or 0
            )
        except Exception:
            total = 0

        self.total = total
        self.completed = index

        op = self._clean(
            event.get(
                "op"
            )
        ).upper()

        target = self._clean(
            event.get(
                "target"
            )
        )

        status = self._clean(
            event.get(
                "status"
            )
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

        duration = self._elapsed(
            elapsed
        )

        symbol = (
            "✓"
            if status == "APPLIED"
            else (
                "○"
                if status.startswith(
                    "SKIPPED"
                )
                else "✗"
            )
        )

        prefix = (
            "  {} {}".format(
                symbol,
                word,
            )
        )

        padding = max(
            1,
            self._width()
            - len(prefix)
            - len(duration),
        )

        self._print(
            prefix
            + " " * padding
            + duration,
            tone=tone,
            bold=(
                status
                != "APPLIED"
            ),
        )

        self._print(
            self._progress_bar(
                index,
                total,
            ),
            tone="accent",
        )

        self._print()

    # ------------------------------------------------------------------
    # Completion graphs
    # ------------------------------------------------------------------

    def _outcome_row(
        self,
        label,
        value,
        largest,
        tone,
    ):
        try:
            value = int(
                value
                or 0
            )
        except Exception:
            value = 0

        largest = max(
            1,
            int(
                largest
                or 1
            ),
        )

        if value:
            filled = max(
                1,
                int(
                    round(
                        self.OUTCOME_BAR_WIDTH
                        * float(value)
                        / float(largest)
                    )
                ),
            )
        else:
            filled = 0

        bar = (
            "█" * filled
            + "░" * (
                self.OUTCOME_BAR_WIDTH
                - filled
            )
        )

        try:
            from rich.text import Text

            text = Text()

            text.append(
                "  {:<8} ".format(
                    label
                ),
                style=PALETTE[tone],
            )

            text.append(
                bar,
                style=PALETTE[tone],
            )

            text.append(
                "  {}".format(
                    value
                ),
                style=PALETTE["text"],
            )

            self._print_text(
                text
            )

        except Exception:
            self._print(
                "  {:<8} {}  {}".format(
                    label,
                    bar,
                    value,
                )
            )

    def _timing_row(
        self,
        op,
        elapsed,
        longest,
    ):
        if longest <= 0:
            length = 1
        else:
            length = max(
                1,
                int(
                    round(
                        self.TIMING_BAR_WIDTH
                        * elapsed
                        / longest
                    )
                ),
            )

        length = min(
            self.TIMING_BAR_WIDTH,
            length,
        )

        bar = (
            "█" * length
        )

        gap = (
            " "
            * (
                self.TIMING_BAR_WIDTH
                - length
            )
        )

        try:
            from rich.text import Text

            text = Text()

            text.append(
                "  {:<8} ".format(
                    str(
                        op
                        or "?"
                    )[:8]
                ),
                style=PALETTE["accent"],
            )

            text.append(
                bar,
                style=PALETTE["accent"],
            )

            text.append(
                gap
            )

            text.append(
                "  {:>6}".format(
                    self._elapsed(
                        elapsed
                    )
                ),
                style=PALETTE["text"],
            )

            self._print_text(
                text
            )

        except Exception:
            self._print(
                "  {:<8} {}{}  {:>6}".format(
                    str(
                        op
                        or "?"
                    )[:8],
                    bar,
                    gap,
                    self._elapsed(
                        elapsed
                    ),
                )
            )

    def _completion(self):
        if self._finished:
            return

        self._finished = True

        self._spinner_finish()
        self._ensure_started()

        clean = (
            self.status == "APPLIED"
            and self.failed == 0
        )

        self._rule()

        self._print()

        if clean:
            self._center(
                "R U N   C L E A N",
                tone="success",
                bold=True,
            )
        else:
            self._center(
                "R U N   F A I L E D",
                tone="danger",
                bold=True,
            )

        meta = (
            "{} operation{} · {} total".format(
                self.completed,
                ""
                if self.completed == 1
                else "s",
                self._elapsed(
                    self.run_elapsed
                ),
            )
        )

        if self.packet_bytes:
            meta += (
                " · {} packet".format(
                    self._bytes(
                        self.packet_bytes
                    )
                )
            )

        self._center(
            meta,
            tone="muted",
        )

        self._print()

        if clean:
            self._center(
                "Run clean. {} operation{} applied with no visible errors.".format(
                    self.completed,
                    ""
                    if self.completed == 1
                    else "s",
                ),
                tone="success",
            )

        else:
            self._center(
                "Forge finished with {} failed operation{}.".format(
                    self.failed,
                    ""
                    if self.failed == 1
                    else "s",
                ),
                tone="danger",
            )

        self._print()

        self._print(
            "Outcome",
            tone="muted",
        )

        largest = max(
            self.applied,
            self.skipped,
            self.failed,
            1,
        )

        self._outcome_row(
            "applied",
            self.applied,
            largest,
            "success",
        )

        self._outcome_row(
            "skipped",
            self.skipped,
            largest,
            "warning",
        )

        self._outcome_row(
            "failed",
            self.failed,
            largest,
            "danger",
        )

        if self.timings:
            self._print()

            self._print(
                "Operation time",
                tone="muted",
            )

            ordered = sorted(
                self.timings,
                key=lambda row: row[2],
                reverse=True,
            )

            longest = max(
                row[2]
                for row in ordered
            )

            visible = ordered[
                :self.MAX_TIMINGS
            ]

            for op, _target, elapsed in visible:
                self._timing_row(
                    op,
                    elapsed,
                    longest,
                )

            overflow = (
                len(ordered)
                - len(visible)
            )

            if overflow > 0:
                self._print(
                    "  +{} more operation{}".format(
                        overflow,
                        ""
                        if overflow == 1
                        else "s",
                    ),
                    tone="muted",
                )

        self._print()

        if clean:
            self._center(
                "🧠  Summary enough",
                tone="success",
                bold=True,
            )

        else:
            self._center(
                "⚠  Inspect return packet",
                tone="warning",
                bold=True,
            )

        self._print()

        self._rule(
            char="─",
        )

    # ------------------------------------------------------------------
    # Forge event callback
    # ------------------------------------------------------------------

    def __call__(
        self,
        event,
    ):
        name = self._clean(
            event.get(
                "event"
            )
        )

        if name == "run_started":
            self.started_at = (
                time.monotonic()
            )

            self.stamp = self._clean(
                event.get(
                    "stamp"
                )
            )

            self.mode = self._clean(
                event.get(
                    "mode"
                )
            )

            self.status = "RUNNING"

            self._ensure_started()
            return

        if name == "parse_started":
            self._ensure_started()

            self._spinner_start(
                "Parsing bundle"
            )
            return

        if name == "parse_finished":
            self._spinner_finish()

            if event.get(
                "success"
            ):
                try:
                    self.total = int(
                        event.get(
                            "op_count"
                        )
                        or 0
                    )
                except Exception:
                    self.total = 0

            return

        if name == "operation_started":
            self._operation_start(
                event
            )
            return

        if name == "operation_finished":
            self._operation_finish(
                event
            )
            return

        if name == "run_finished":
            self.status = (
                self._clean(
                    event.get(
                        "status"
                    )
                ).upper()
                or "FINISHED"
            )

            try:
                self.run_elapsed = float(
                    event.get(
                        "elapsed_seconds"
                    )
                    or (
                        time.monotonic()
                        - self.started_at
                    )
                )
            except Exception:
                self.run_elapsed = (
                    time.monotonic()
                    - self.started_at
                )

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

            if not self.total:
                self.total = (
                    self.completed
                )

            self._completion()
            return

    def abort(self):
        self._spinner_finish()

        self.status = "FAILED"

        if not self.run_elapsed:
            self.run_elapsed = (
                time.monotonic()
                - self.started_at
            )

        if self.failed <= 0:
            self.failed = 1

        self._completion()

    # ------------------------------------------------------------------
    # Clipboard handoff
    # ------------------------------------------------------------------

    def print_clipboard_status(
        self,
        ok,
    ):
        self._spinner_finish()

        self._print()

        if ok:
            self._center(
                "✓ Return packet copied to clipboard",
                tone="success",
                bold=True,
            )

            self._center(
                "paste back into ChatGPT",
                tone="muted",
            )

        else:
            self._center(
                "✗ Clipboard update failed",
                tone="danger",
                bold=True,
            )
