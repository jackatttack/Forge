"""Forge Landing panel: the screen a Forge run ends on, docked in the console.

Ways in:
    show_live_landing(live)     docks when the run starts; op rows, progress
                                and the running op fill in from Forge's events
    finish_live_landing(model)  turns the live landing into the full one when
                                the run ends: verdict, outcome bars, footer,
                                tappable rows with detail cards
    show_landing(model)         docks a finished run in one go (fallback, labs)

Look: Forge's live console palette, spaced titles, pink double rules, Menlo.
Motion: one update() clock on the main thread draws everything; Forge's
event thread only records plain data (live.py). ui.animate is used for
frame and alpha only, never with a completion, and ui.delay is never used.
Presentation only: never changes the run or the clipboard packet unless the
user taps a copy button.
"""
import builtins
import math
import os
import time

import clipboard
import console
import editor
import ui
from objc_util import ObjCClass, on_main_thread

from .detail_html import change_html
from .model import TONE_GLYPH, spaced, status_tone

# --- Look -------------------------------------------------------------------
HEX = {
    'accent': '#5AA9FF', 'border': '#E91E63', 'danger': '#FF5A5F',
    'muted': '#9FB4C9', 'success': '#4CD964', 'text': '#EEF6FF',
    'warning': '#FFD166', 'orange': '#FF9F43', 'cyan': '#5DEBFF',
    'panel': '#0D0F14', 'card': '#151922', 'track': '#232936',
}
FONT = 'Menlo'
BOLD = 'Menlo-Bold'
SIDE_MARGIN = 10
TOP_MARGIN = 10
INPUT_BAR_CLEARANCE = 90
COLLAPSED_HEIGHT = 52
ROW_HEIGHT = 42
ROWS_TOP = 88
BOTTOM_BLOCK_HEIGHT = 214     # verdict/outcomes/footer, or the live block
OUTCOME_NAMES = (('success', 'applied'), ('warning', 'skipped'), ('danger', 'failed'))

# --- Motion (seconds) -------------------------------------------------------
HEADER_FADE = 0.25
ROW_START = 0.2
ROW_STAGGER = 0.09
ROWS_MAX_SPREAD = 1.2         # many ops share this window instead of queuing
ROW_FADE = 0.22
ROW_SLIDE = 14
BAR_GROW = 0.35
VERDICT_DELAY = 0.15
VERDICT_POP = 0.3
VERDICT_START_SCALE = 1.25
OUTCOME_GROW = 0.45
DETAIL_SLIDE = 0.28
COLLAPSE_SECONDS = 0.3
OPEN_SELECTION_DELAY = 0.9    # the editor needs a moment after open_file
LIVE_ROW_FADE = 0.25
LIVE_PROGRESS_EASE = 0.2      # share of the remaining gap closed each tick
PULSE_SPEED = 5.0

# --- Docking bookkeeping ----------------------------------------------------
LANDING_TAG = 47011           # every docked landing carries this view tag
LANDING_EXTRA_INSET = COLLAPSED_HEIGHT + 12
KEEP_ALIVE_NAME = '_forge_landing'
BASE_INSET_NAME = '_forge_landing_base_inset'


def ease_out(progress):
    progress = min(max(progress, 0.0), 1.0)
    return 1 - (1 - progress) ** 3


def short_text(text, width):
    text = str(text or '').replace('\n', ' ')
    return text if len(text) <= width else '…' + text[-(width - 1):]


def line_start_offset(text, line_number):
    offset = 0
    for _ in range(max(line_number, 1) - 1):
        next_newline = text.find('\n', offset)
        if next_newline < 0:
            return len(text)
        offset = next_newline + 1
    return offset


# --- Finding the console ----------------------------------------------------
def class_name(view):
    name = view._get_objc_classname()
    return name.decode() if isinstance(name, bytes) else str(name)


def search_views(view, inside_editor):
    name = class_name(view)
    if name == 'OMTextEditorView':
        inside_editor = True
    elif name == 'OMTextView' and not inside_editor:
        return view
    for subview in view.subviews():
        found = search_views(subview, inside_editor)
        if found is not None:
            return found
    return None


def find_console_text_view():
    """The console is the first OMTextView with no OMTextEditorView above it."""
    app = ObjCClass('UIApplication').sharedApplication()
    for window in app.windows():
        found = search_views(window, inside_editor=False)
        if found is not None:
            return found
    return None


# --- The panel --------------------------------------------------------------
class LandingPanel(ui.View):
    """The landing card: a header and rows area, filled live or from a model."""

    def __init__(self, width, height, text_view, base_bottom, stamp='', mode='dev', live=None):
        self.text_view = text_view
        self.base_bottom = base_bottom
        self.live = live
        self.model = None
        self.expanded = True
        self.full_frame = None
        self.pending_selection = None
        self.detail = None

        # Arrival (finished-run) animation state
        self.started = None
        self.arrival_done = True
        self.include_header = False
        self.rows_preshown = False
        self.header_views = []
        self.row_items = []         # (row view, bar view or None, bar final width)
        self.verdict = None
        self.verdict_views = []
        self.outcome_bars = []      # (bar view, final width)
        self.late_views = []

        # Live state
        self.live_views = []
        self.live_version = -1
        self.live_rows = 0
        self.live_slowest = 0.001
        self.live_fraction = 0.0

        self.background_color = HEX['panel']
        self.corner_radius = 14
        self.border_width = 1
        self.border_color = HEX['border']
        self.frame = (0, 0, width, height)
        self.build_header(stamp, mode)
        rows_height = max(height - BOTTOM_BLOCK_HEIGHT - ROWS_TOP, ROW_HEIGHT)
        self.scroll = ui.ScrollView(frame=(0, ROWS_TOP, width, rows_height))
        self.add_subview(self.scroll)
        if live is not None:
            self.build_live_block()
        self.update_interval = 1 / 30   # set once, never changed

    # Building blocks
    def label(self, parent, text, frame, tone='text', size=12, bold=False,
              align=ui.ALIGN_LEFT, lines=1):
        view = ui.Label(frame=frame)
        view.text = text
        view.text_color = HEX[tone]
        view.font = (BOLD if bold else FONT, size)
        view.alignment = align
        view.number_of_lines = lines
        parent.add_subview(view)
        return view

    def button(self, parent, title, frame, action, tone='accent'):
        # Title before frame: a Button built with a title shrink-wraps to it
        # and ignores the frame.
        view = ui.Button()
        view.title = title
        view.font = (BOLD, 12)
        view.tint_color = HEX[tone]
        view.border_color = HEX[tone]
        view.border_width = 1
        view.corner_radius = 8
        view.action = action
        view.frame = frame
        parent.add_subview(view)
        return view

    def rule(self, y):
        """The renderer's pink double rule."""
        views = []
        for offset, thickness in ((0, 2), (5, 1)):
            line = ui.View(frame=(12, y + offset, self.width - 24, thickness))
            line.background_color = HEX['border']
            self.add_subview(line)
            views.append(line)
        return views

    def bar(self, parent, x, y, width, height, tone):
        track = ui.View(frame=(x, y, width, height))
        track.background_color = HEX['track']
        track.corner_radius = height / 2
        parent.add_subview(track)
        fill = ui.View(frame=(x, y, 0, height))
        fill.background_color = HEX[tone]
        fill.corner_radius = height / 2
        parent.add_subview(fill)
        return track, fill

    # Layout
    @staticmethod
    def subtitle_text(stamp, mode):
        return '%s  ·  %s' % (str(mode or 'dev').upper(), stamp or 'STARTING')

    def build_header(self, stamp, mode):
        width = self.width
        self.title = self.label(self, spaced('FORGE'), (60, 10, width - 120, 26),
                                'accent', 20, True, ui.ALIGN_CENTER)
        self.subtitle = self.label(self, self.subtitle_text(stamp, mode),
                                   (60, 34, width - 120, 16), 'muted', 11, False,
                                   ui.ALIGN_CENTER)
        self.collapse_button = self.button(self, '▾', (width - 84, 10, 34, 28),
                                           self.toggle_collapse, 'muted')
        close = self.button(self, '✕', (width - 44, 10, 34, 28), self.close, 'muted')
        section = self.label(self, 'OPERATIONS', (14, 70, 200, 16), 'muted', 11, True)
        self.header_views = [self.title, self.subtitle, self.collapse_button, close,
                             section] + self.rule(58)

    def build_row(self, index, total, glyph, tone, op, target, seconds, slowest, row=None):
        """One op row in the scroll list; row (an OpRow) makes it tappable."""
        width = self.width
        view = ui.View(frame=(0, index * ROW_HEIGHT, width, ROW_HEIGHT))
        self.scroll.add_subview(view)
        self.label(view, glyph, (12, 4, 18, 18), tone, 14, True)
        self.label(view, '%02d/%02d' % (index + 1, max(total, index + 1)),
                   (32, 5, 46, 16), 'muted', 11)
        has_time = seconds is not None
        op_width = width - 80 - (164 if has_time else 16)
        self.label(view, op, (80, 4, op_width, 18), tone, 13, True)
        self.label(view, short_text(target, int((width - 44) / 6.6)),
                   (32, 23, width - 44, 14), 'muted', 10)
        fill, final_width = None, 0
        if has_time:
            track_x, track_width = width - 152, 92
            _, fill = self.bar(view, track_x, 9, track_width, 7, 'accent')
            final_width = max(track_width * min(seconds / max(slowest, 0.001), 1.0), 3)
            self.label(view, '%.2fs' % seconds, (width - 56, 5, 48, 16),
                       'muted', 11, False, ui.ALIGN_RIGHT)
        if row is not None:
            tap = ui.Button(frame=(0, 0, width, ROW_HEIGHT))
            tap.action = lambda sender, row=row: self.open_detail(row)
            view.add_subview(tap)
        self.scroll.content_size = (width, (index + 1) * ROW_HEIGHT + 6)
        return view, fill, final_width

    def build_model_rows(self, preshown):
        for view in list(self.scroll.subviews):
            self.scroll.remove_subview(view)
        self.row_items = []
        rows = self.model.rows
        for index, row in enumerate(rows):
            view, fill, final_width = self.build_row(
                index, len(rows), row.glyph, row.tone, row.op, row.target,
                row.seconds, self.model.slowest, row=row)
            view.alpha = 1.0 if preshown else 0.0
            self.row_items.append((view, fill, final_width))
        self.rows_preshown = preshown

    def build_live_block(self):
        width, top = self.width, self.height - BOTTOM_BLOCK_HEIGHT
        views = self.rule(top)
        self.live_title = self.label(self, spaced('RUNNING'), (10, top + 14, width - 20, 30),
                                     'accent', 20, True, ui.ALIGN_CENTER)
        self.live_count = self.label(self, 'starting', (10, top + 46, width - 20, 16),
                                     'muted', 11, False, ui.ALIGN_CENTER)
        self.live_track_width = width - 28
        track, self.live_fill = self.bar(self, 14, top + 74, self.live_track_width, 10, 'accent')
        self.active_label = self.label(self, '', (14, top + 98, width - 100, 18), 'cyan', 13, True)
        self.active_seconds = self.label(self, '', (width - 86, top + 98, 72, 18),
                                         'muted', 12, False, ui.ALIGN_RIGHT)
        self.active_target = self.label(self, '', (14, top + 118, width - 28, 14), 'muted', 10)
        pulse_track, self.pulse = self.bar(self, 14, top + 142, width - 28, 4, 'cyan')
        self.pulse.width = width - 28
        self.pulse.alpha = 0.0
        self.live_views = views + [self.live_title, self.live_count, track, self.live_fill,
                                   self.active_label, self.active_seconds,
                                   self.active_target, pulse_track, self.pulse]

    def build_bottom_block(self):
        width, model = self.width, self.model
        top = self.height - BOTTOM_BLOCK_HEIGHT
        verdict_text, verdict_tone = model.verdict
        rules = self.rule(top)
        self.verdict = self.label(self, spaced(verdict_text), (10, top + 14, width - 20, 30),
                                  verdict_tone, 20, True, ui.ALIGN_CENTER)
        summary = self.label(self, model.summary_line(), (10, top + 46, width - 20, 16),
                             'muted', 11, False, ui.ALIGN_CENTER)
        self.verdict_views = rules + [self.verdict, summary]

        y = top + 74
        biggest = max(max(model.counts.values()), 1)
        track_width = width - 168
        self.outcome_bars = []
        self.late_views = []
        for tone, name in OUTCOME_NAMES:
            count = model.counts[tone]
            self.late_views.append(self.label(self, name, (14, y - 3, 84, 16), tone, 12))
            track, fill = self.bar(self, 100, y, track_width, 9, tone)
            self.late_views.append(track)
            self.outcome_bars.append((fill, track_width * count / float(biggest)))
            self.late_views.append(self.label(self, str(count), (width - 56, y - 3, 40, 16),
                                              'text', 12, False, ui.ALIGN_RIGHT))
            y += 20

        button_width = (width - 14 * 4) / 3.0
        footer_y = self.height - 46
        for index, (title, action) in enumerate((('Copy packet', self.copy_packet),
                                                 ('Last edit', self.open_last_edit),
                                                 ('Copy DIFF', self.copy_diff))):
            x = 14 + index * (button_width + 14)
            self.late_views.append(self.button(self, title, (x, footer_y, button_width, 32),
                                               action))
        for view in self.verdict_views + self.late_views:
            view.alpha = 0.0

    def begin_arrival(self, include_header):
        self.include_header = include_header
        if include_header:
            for view in self.header_views:
                view.alpha = 0.0
        self.started = None
        self.arrival_done = False

    def show_model(self, model):
        """Fill a fresh panel from a finished run, with the full arrival."""
        self.model = model
        self.build_model_rows(preshown=False)
        self.build_bottom_block()
        self.begin_arrival(include_header=True)

    def finish(self, model):
        """Turn the live landing into the full landing for the finished run."""
        self.model = model
        for view in self.live_views:
            self.remove_subview(view)
        self.live_views = []
        self.subtitle.text = self.subtitle_text(model.stamp, model.mode)
        self.build_model_rows(preshown=True)
        self.build_bottom_block()
        self.begin_arrival(include_header=False)

    # The frame clock
    def update(self):
        if self.objc_instance.superview() is None:
            return
        now = time.time()
        self.apply_pending_selection(now)
        if self.live is not None and self.model is None:
            self.update_live(now)
        elif not self.arrival_done:
            self.update_arrival(now)

    def update_live(self, now):
        snapshot = self.live.snapshot()
        finished = snapshot['finished']
        total = max(int(snapshot['total'] or 0), len(finished), 1)
        if snapshot['version'] != self.live_version:
            self.live_version = snapshot['version']
            for data in finished[self.live_rows:]:
                self.add_live_row(self.live_rows, total, data)
                self.live_rows += 1
            self.live_count.text = '%d / %d operations' % (len(finished), total)
            self.live_fraction = len(finished) / float(total)
            if snapshot['stamp']:
                self.subtitle.text = self.subtitle_text(snapshot['stamp'], snapshot['mode'])

        shown = self.live_fill.width / float(self.live_track_width)
        shown += (self.live_fraction - shown) * LIVE_PROGRESS_EASE
        self.live_fill.width = self.live_track_width * shown

        active = snapshot['active']
        if active:
            self.active_label.text = '▶  %s' % active['op']
            self.active_target.text = short_text(active['target'], int((self.width - 28) / 6.6))
            self.active_seconds.text = '%.1fs' % (now - active['started'])
            self.pulse.alpha = 0.25 + 0.35 * (1 + math.sin(now * PULSE_SPEED)) / 2
        else:
            self.active_label.text = ''
            self.active_target.text = ''
            self.active_seconds.text = ''
            self.pulse.alpha = 0.0

    def add_live_row(self, index, total, data):
        seconds = data.get('seconds')
        self.live_slowest = max(self.live_slowest, seconds or 0)
        tone = status_tone(data.get('status'))
        view, fill, final_width = self.build_row(index, total, TONE_GLYPH[tone], tone,
                                                 data.get('op', '?'), data.get('target', ''),
                                                 seconds, self.live_slowest)
        view.alpha = 0.0
        view.x = -ROW_SLIDE

        def arrive():
            view.alpha = 1.0
            view.x = 0
            if fill is not None:
                fill.width = final_width
        ui.animate(arrive, LIVE_ROW_FADE)
        overflow = (index + 1) * ROW_HEIGHT + 6 - self.scroll.height
        if overflow > 0:
            self.scroll.content_offset = (0, overflow)

    def update_arrival(self, now):
        if self.started is None:
            self.started = now
        t = now - self.started
        if self.include_header:
            for view in self.header_views:
                view.alpha = ease_out(t / HEADER_FADE)

        count = max(len(self.row_items), 1)
        if self.rows_preshown:
            for view, fill, final_width in self.row_items:
                if fill is not None:
                    fill.width = final_width * ease_out(t / BAR_GROW)
            verdict_start = VERDICT_DELAY
        else:
            stagger = min(ROW_STAGGER, ROWS_MAX_SPREAD / count)
            for index, (view, fill, final_width) in enumerate(self.row_items):
                appear = ROW_START + index * stagger
                progress = ease_out((t - appear) / ROW_FADE)
                view.alpha = progress
                view.x = -ROW_SLIDE * (1 - progress)
                if fill is not None:
                    fill.width = final_width * ease_out((t - appear - ROW_FADE * 0.5) / BAR_GROW)
            verdict_start = ROW_START + (count - 1) * stagger + ROW_FADE + VERDICT_DELAY

        pop = ease_out((t - verdict_start) / VERDICT_POP)
        for view in self.verdict_views:
            view.alpha = pop
        scale = VERDICT_START_SCALE - (VERDICT_START_SCALE - 1) * pop
        self.verdict.transform = ui.Transform.scale(scale, scale)

        outcome_start = verdict_start + 0.1
        grow = ease_out((t - outcome_start) / OUTCOME_GROW)
        for fill, final_width in self.outcome_bars:
            fill.width = final_width * grow
        for view in self.late_views:
            view.alpha = grow
        if t > outcome_start + OUTCOME_GROW + 0.05:
            self.arrival_done = True

    # Collapse and close
    def toggle_collapse(self, sender):
        self.expanded = not self.expanded
        if self.full_frame is None:
            self.full_frame = tuple(self.frame)
        x, y, width, height = self.full_frame
        bottom = y + height
        if self.expanded:
            target = self.full_frame
            self.title.text = spaced('FORGE')
            self.title.text_color = HEX['accent']
        else:
            target = (x, bottom - COLLAPSED_HEIGHT, width, COLLAPSED_HEIGHT)
            verdict_text, verdict_tone = (self.model.verdict if self.model is not None
                                          else ('RUNNING', 'accent'))
            self.title.text = 'FORGE  ·  ' + verdict_text
            self.title.text_color = HEX[verdict_tone]

        def resize():
            self.frame = target
        ui.animate(resize, COLLAPSE_SECONDS)
        sender.title = '▾' if self.expanded else '▴'

    def close(self, sender=None):
        try:
            insets = self.text_view.contentInset()
            self.text_view.setContentInset_((insets.top, insets.left,
                                             self.base_bottom, insets.right))
        except Exception:
            pass
        self.objc_instance.removeFromSuperview()
        if getattr(builtins, KEEP_ALIVE_NAME, None) is self:
            setattr(builtins, KEEP_ALIVE_NAME, None)

    # Detail card
    def open_detail(self, row):
        width, height = self.width, self.height
        if self.detail is not None:
            self.remove_subview(self.detail)
        card = ui.View(frame=(width, 0, width, height))
        card.background_color = HEX['panel']
        self.label(card, '%s  %s' % (row.glyph, row.op), (14, 12, width - 140, 22),
                   row.tone, 16, True)
        self.label(card, row.status, (width - 130, 14, 116, 18), row.tone, 11, True,
                   ui.ALIGN_RIGHT)
        self.label(card, row.target, (14, 38, width - 28, 30), 'muted', 10, lines=2)
        self.label(card, row.message, (14, 70, width - 28, 32), 'text', 11, lines=2)
        views = ui.SegmentedControl(frame=(12, 106, width - 24, 30))
        views.segments = ['Change', 'Result']
        views.selected_index = 0
        views.tint_color = HEX['accent']
        card.add_subview(views)
        preview = ui.TextView(frame=(12, 144, width - 24, height - 204))
        texts = (row.change_text()[:12000], row.preview[:12000])
        preview.text = texts[0]
        preview.font = (FONT, 10)
        preview.text_color = HEX['text']
        preview.background_color = HEX['card']
        preview.editable = False
        preview.corner_radius = 8
        card.add_subview(preview)

        # Rich Change view; the plain text view stays as the fallback.
        try:
            html = change_html(row, self.model.project_root)
        except Exception:
            html = None
        web = None
        if html:
            web = ui.WebView(frame=preview.frame)
            web.background_color = HEX['card']
            web.corner_radius = 8
            web.load_html(html)
            card.add_subview(web)
            preview.hidden = True

        def switch_view(sender):
            showing_change = sender.selected_index == 0
            preview.text = texts[sender.selected_index]
            if web is not None:
                web.hidden = not showing_change
                preview.hidden = showing_change
        views.action = switch_view

        button_width = (width - 42) / 2.0
        self.button(card, 'Back', (14, height - 48, button_width, 34), self.close_detail, 'muted')
        if row.path:
            self.button(card, 'Open at line %d' % row.start_line,
                        (28 + button_width, height - 48, button_width, 34),
                        lambda sender, row=row: self.open_location(row))
        self.add_subview(card)
        self.detail = card

        def slide_in():
            card.x = 0
        ui.animate(slide_in, DETAIL_SLIDE)

    def close_detail(self, sender):
        card = self.detail

        def slide_out():
            card.x = self.width
        ui.animate(slide_out, DETAIL_SLIDE)

    # Actions
    def copy_packet(self, sender):
        clipboard.set(self.model.packet)
        console.hud_alert('Packet copied')

    def copy_diff(self, sender):
        clipboard.set('ENV: pythonista\nDIFF %s' % self.model.stamp)
        console.hud_alert('DIFF bundle copied')

    def open_last_edit(self, sender):
        row = self.model.last_edit()
        if row is None:
            console.hud_alert('No file in this run', 'error')
            return
        self.open_location(row)

    def open_location(self, row):
        full_path = os.path.join(self.model.project_root, row.path)
        editor.open_file(full_path, new_tab=True)
        # Selecting must wait until the editor has loaded the file; the frame
        # clock applies it when due (never ui.delay).
        self.pending_selection = (time.time() + OPEN_SELECTION_DELAY, full_path,
                                  row.start_line, row.end_line)

    def apply_pending_selection(self, now):
        if not self.pending_selection or now < self.pending_selection[0]:
            return
        _, full_path, first, last = self.pending_selection
        self.pending_selection = None
        try:
            if os.path.realpath(editor.get_path() or '') != os.path.realpath(full_path):
                return
            text = editor.get_text() or ''
            start = line_start_offset(text, first)
            end = line_start_offset(text, last + 1)
            if end > start and text[end - 1:end] == '\n':
                end -= 1
            editor.set_selection(start, max(start, end))
        except Exception:
            pass


# --- Docking ----------------------------------------------------------------
def prepare_dock():
    """Find the console and remove every docked landing.

    Landings are found by view tag, so one whose Python object was lost (an
    orphan from an earlier run) is removed too. Returns (text_view, base
    bottom inset), or (None, None) when there is no console. The base inset
    is remembered so docking never stacks padding run after run.
    """
    text_view = find_console_text_view()
    if text_view is None:
        return None, None
    had_landing = False
    for view in list(text_view.superview().subviews()):
        if view.tag() == LANDING_TAG:
            view.removeFromSuperview()
            had_landing = True
    setattr(builtins, KEEP_ALIVE_NAME, None)
    current = text_view.contentInset().bottom
    stored = getattr(builtins, BASE_INSET_NAME, None)
    if not had_landing:
        base = current
        setattr(builtins, BASE_INSET_NAME, base)
    elif stored is not None:
        base = stored
    else:
        base = max(current - LANDING_EXTRA_INSET, 0)
    return text_view, base


def panel_size(text_view):
    frame = text_view.frame()
    return (frame.size.width - SIDE_MARGIN * 2,
            frame.size.height - TOP_MARGIN - INPUT_BAR_CLEARANCE)


def attach(panel, text_view, base_bottom):
    frame = text_view.frame()
    panel.frame = (frame.origin.x + SIDE_MARGIN, frame.origin.y + TOP_MARGIN,
                   panel.width, panel.height)
    insets = text_view.contentInset()
    text_view.setContentInset_((insets.top, insets.left,
                                base_bottom + LANDING_EXTRA_INSET, insets.right))
    panel.objc_instance.setTag_(LANDING_TAG)
    text_view.superview().addSubview_(panel.objc_instance)
    setattr(builtins, KEEP_ALIVE_NAME, panel)


@on_main_thread
def show_live_landing(live):
    """Dock an empty landing at run start; it fills in from live's events."""
    try:
        text_view, base = prepare_dock()
        if text_view is None:
            return False
        width, height = panel_size(text_view)
        snapshot = live.snapshot()
        panel = LandingPanel(width, height, text_view, base, snapshot['stamp'],
                             snapshot['mode'], live=live)
        panel.alpha = 0.0
        attach(panel, text_view, base)

        def appear():
            panel.alpha = 1.0
        ui.animate(appear, HEADER_FADE)
        return True
    except Exception:
        return False


@on_main_thread
def finish_live_landing(model, collapsed=False):
    """Complete the docked live landing. False when there is none to finish."""
    try:
        panel = getattr(builtins, KEEP_ALIVE_NAME, None)
        if panel is None or panel.live is None or panel.model is not None:
            return False
        if panel.objc_instance.superview() is None:
            return False
        panel.finish(model)
        if collapsed and panel.expanded:
            panel.toggle_collapse(panel.collapse_button)
        return True
    except Exception:
        return False


@on_main_thread
def show_landing(model, collapsed=False):
    """Dock a complete landing for a finished run, replacing any earlier one.

    collapsed=True docks it as the slim verdict bar, so console output an op
    printed stays visible. Returns False when the console cannot be found.
    """
    try:
        text_view, base = prepare_dock()
        if text_view is None:
            return False
        width, height = panel_size(text_view)
        panel = LandingPanel(width, height, text_view, base, model.stamp, model.mode)
        panel.show_model(model)
        attach(panel, text_view, base)
        if collapsed:
            panel.toggle_collapse(panel.collapse_button)
        return True
    except Exception as error:
        print('Forge Landing failed: %r' % error)
        return False