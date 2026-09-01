# -*- coding: utf-8 -*-
# portable-forge-pythonide-live-ui-v1
"""
Rich live dashboard for Portable Forge on PythonIDE.

Presentation only. Forge's canonical packet is produced separately and remains
plain text for the clipboard.

Important PythonIDE detail:
The Rich Console deliberately captures the current sys.stdout object when this
dashboard is constructed. Forge's RUN operation may temporarily replace the
global sys.stdout while collecting child-script output. Retaining PythonIDE's
original stream keeps the live dashboard visible without contaminating RUN
stdout with Rich terminal control sequences.
"""

import sys
import time


class ForgeLiveUI:
    MAX_HISTORY = 8
    BAR_WIDTH = 28

    def __init__(self):
        self.available = False
        self.console = None
        self.live = None

        self.stamp = ""
        self.mode = ""
        self.total = 0
        self.completed = 0
        self.status = "STARTING"
        self.started_at = time.monotonic()

        self.parse_state = "waiting"
        self.current = None
        self.history = []

        try:
            from rich.console import Console
            from rich.live import Live

            terminal = sys.stdout

            self.console = Console(
                file=terminal,
            )

            self.live = Live(
                self._render(),
                console=self.console,
                refresh_per_second=10,
                transient=False,
            )

            self.available = True

        except Exception:
            self.available = False
            self.console = None
            self.live = None

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

    @classmethod
    def _shorten(
        cls,
        value,
        limit=52,
    ):
        text = cls._clean(
            value
        )

        if len(text) <= limit:
            return text

        return (
            text[: limit - 1]
            + "…"
        )

    @classmethod
    def _bar(
        cls,
        completed,
        total,
    ):
        try:
            completed = int(
                completed
                or 0
            )
            total = int(
                total
                or 0
            )
        except Exception:
            completed = 0
            total = 0

        if total <= 0:
            filled = 0

        else:
            ratio = max(
                0.0,
                min(
                    1.0,
                    float(completed)
                    / float(total),
                ),
            )

            filled = int(
                round(
                    cls.BAR_WIDTH
                    * ratio
                )
            )

        return (
            "━" * filled
            + "─"
            * (
                cls.BAR_WIDTH
                - filled
            )
        )

    def _render(self):
        try:
            from rich.console import Group
            from rich.panel import Panel
            from rich.spinner import Spinner
            from rich.table import Table
            from rich.text import Text

        except Exception:
            return ""

        elapsed = (
            time.monotonic()
            - self.started_at
        )

        header = Table.grid(
            expand=True,
        )
        header.add_column()
        header.add_column(
            justify="right",
        )

        title = Text(
            "FORGE",
            style="bold cyan",
        )

        meta = Text()

        if self.stamp:
            meta.append(
                self.stamp,
                style="dim",
            )

        if self.mode:
            if self.stamp:
                meta.append(
                    "  "
                )

            meta.append(
                self.mode.upper(),
                style="bold cyan",
            )

        header.add_row(
            title,
            meta,
        )

        progress = Text()

        if self.status == "APPLIED":
            progress.append(
                "✓ ",
                style="bold green",
            )

        elif self.status.startswith(
            "FAILED"
        ):
            progress.append(
                "✗ ",
                style="bold red",
            )

        else:
            progress.append(
                "● ",
                style="bold cyan",
            )

        progress.append(
            self._bar(
                self.completed,
                self.total,
            ),
            style=(
                "green"
                if self.status == "APPLIED"
                else "cyan"
            ),
        )

        progress.append(
            "  {}/{}".format(
                self.completed,
                self.total
                or "?",
            ),
            style="bold white",
        )

        progress.append(
            "  {:.1f}s".format(
                elapsed
            ),
            style="dim",
        )

        if self.status == "APPLIED":
            status_style = "bold green"

        elif self.status.startswith(
            "FAILED"
        ):
            status_style = "bold red"

        else:
            status_style = "bold cyan"

        header.add_row(
            progress,
            Text(
                self.status,
                style=status_style,
            ),
        )

        body = Table(
            box=None,
            show_header=False,
            pad_edge=False,
            expand=True,
        )

        body.add_column(
            width=2,
            no_wrap=True,
        )
        body.add_column(
            width=9,
            no_wrap=True,
        )
        body.add_column(
            ratio=1,
        )
        body.add_column(
            justify="right",
            width=8,
            no_wrap=True,
        )

        history = self.history[
            -self.MAX_HISTORY:
        ]

        for row in history:
            status = row.get(
                "status",
                "",
            )

            if status == "APPLIED":
                symbol = "✓"
                style = "green"

            elif status.startswith(
                "SKIPPED"
            ):
                symbol = "○"
                style = "yellow"

            else:
                symbol = "✗"
                style = "red"

            body.add_row(
                Text(
                    symbol,
                    style=style,
                ),
                Text(
                    self._clean(
                        row.get(
                            "op"
                        )
                    ),
                    style=style,
                ),
                Text(
                    self._shorten(
                        row.get(
                            "target"
                        )
                    ),
                    style="white",
                ),
                Text(
                    self._elapsed(
                        row.get(
                            "elapsed_seconds"
                        )
                    ),
                    style="dim",
                ),
            )

        current_renderable = None

        if not self.status.startswith(
            "FAILED"
        ) and self.status != "APPLIED":

            if self.parse_state == "running":
                current_renderable = Spinner(
                    "dots",
                    text=Text(
                        "Parsing Forge bundle",
                        style="bold cyan",
                    ),
                    style="cyan",
                )

            elif self.current:
                op = self._clean(
                    self.current.get(
                        "op"
                    )
                )

                target = self._shorten(
                    self.current.get(
                        "target"
                    ),
                    limit=58,
                )

                text = Text()
                text.append(
                    "{:<9}".format(
                        op
                    ),
                    style="bold cyan",
                )

                if target:
                    text.append(
                        "  " + target,
                        style="white",
                    )

                current_renderable = Spinner(
                    "dots",
                    text=text,
                    style="cyan",
                )

        footer = None

        if self.status == "APPLIED":
            footer = Text()
            footer.append(
                "✓ Forge complete",
                style="bold green",
            )
            footer.append(
                "  ·  {} operation{}".format(
                    self.completed,
                    (
                        ""
                        if self.completed == 1
                        else "s"
                    ),
                ),
                style="green",
            )

        elif self.status.startswith(
            "FAILED"
        ):
            footer = Text()
            footer.append(
                "✗ Forge finished",
                style="bold red",
            )
            footer.append(
                "  ·  " + self.status,
                style="red",
            )

        parts = [
            header,
        ]

        if history:
            parts.extend(
                [
                    Text(""),
                    body,
                ]
            )

        if current_renderable is not None:
            parts.extend(
                [
                    Text(""),
                    current_renderable,
                ]
            )

        if footer is not None:
            parts.extend(
                [
                    Text(""),
                    footer,
                ]
            )

        if self.status == "APPLIED":
            border_style = "green"

        elif self.status.startswith(
            "FAILED"
        ):
            border_style = "red"

        else:
            border_style = "cyan"

        return Panel(
            Group(
                *parts
            ),
            border_style=border_style,
            padding=(
                0,
                1,
            ),
        )

    def _refresh(self):
        if not self.available:
            return

        try:
            self.live.update(
                self._render(),
                refresh=True,
            )
        except Exception:
            pass

    def _start(self):
        if not self.available:
            return

        try:
            if not self.live.is_started:
                self.live.start(
                    refresh=True
                )

        except Exception:
            try:
                self.live.start()
            except Exception:
                self.available = False

    def _stop(self):
        if not self.available:
            return

        try:
            self.live.update(
                self._render(),
                refresh=True,
            )
            self.live.stop()

        except Exception:
            pass

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
            self.started_at = time.monotonic()

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

            self._start()
            self._refresh()
            return

        if name == "parse_started":
            self.parse_state = "running"
            self._refresh()
            return

        if name == "parse_finished":
            if event.get(
                "success"
            ):
                self.parse_state = "complete"
                self.total = int(
                    event.get(
                        "op_count"
                    )
                    or 0
                )

            else:
                self.parse_state = "failed"

            self._refresh()
            return

        if name == "operation_started":
            self.current = {
                "index": event.get(
                    "index"
                ),
                "total": event.get(
                    "total"
                ),
                "op": event.get(
                    "op"
                ),
                "target": event.get(
                    "target"
                ),
            }

            try:
                self.total = int(
                    event.get(
                        "total"
                    )
                    or self.total
                )
            except Exception:
                pass

            self._refresh()
            return

        if name == "operation_finished":
            self.history.append(
                {
                    "index": event.get(
                        "index"
                    ),
                    "total": event.get(
                        "total"
                    ),
                    "op": event.get(
                        "op"
                    ),
                    "target": event.get(
                        "target"
                    ),
                    "status": self._clean(
                        event.get(
                            "status"
                        )
                    ).upper(),
                    "elapsed_seconds": event.get(
                        "elapsed_seconds"
                    ),
                }
            )

            try:
                self.completed = int(
                    event.get(
                        "index"
                    )
                    or len(
                        self.history
                    )
                )

            except Exception:
                self.completed = len(
                    self.history
                )

            self.current = None
            self._refresh()
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

            self.current = None

            if not self.total:
                self.total = self.completed

            self._stop()
            return

    def abort(self):
        self.status = "FAILED"
        self.current = None
        self._stop()

    def print_clipboard_status(
        self,
        ok,
    ):
        if self.console is None:
            if ok:
                print(
                    "Forge return packet copied to clipboard."
                )
            else:
                print(
                    "Forge ran, but clipboard update failed."
                )
            return

        try:
            from rich.text import Text

            self.console.print()

            if ok:
                text = Text()
                text.append(
                    "✓ ",
                    style="bold green",
                )
                text.append(
                    "Return packet copied to clipboard",
                    style="green",
                )
                text.append(
                    "  ·  paste back into ChatGPT",
                    style="dim",
                )

            else:
                text = Text()
                text.append(
                    "✗ ",
                    style="bold red",
                )
                text.append(
                    "Clipboard update failed",
                    style="red",
                )

            self.console.print(
                text
            )

        except Exception:
            if ok:
                print(
                    "Forge return packet copied to clipboard."
                )
            else:
                print(
                    "Forge ran, but clipboard update failed."
                )