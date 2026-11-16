# -*- coding: utf-8 -*-
"""Anvil's window: one editorkit window that shows a Forge run and acts on taps.

    from anvil import landing
    landing.show_run(model, items)     # model: Forge's LandingModel; items: items.py

One window (key 'anvil') is kept and reused: a new run redraws its page and
brings it forward. It lands over the console, where a run ends; if the
console cannot take it, it opens over the code.

Pages: Run (page.py), Runs (runs_page.py: Forge's recent runs, read by
history.py; ◀ ▶ on the run page step through them too) and Projects
(projects_page.py: the registered projects and notes left on them).
🧰 in the header opens the Toolbox.

What the bundle asked for (items) shows as Waiting for you. Answers are
saved beside the run as soon as they are given. A single OPEN opens its
file a moment after the landing shows, as EDITOR's quick open always has.

Typing (an ASK's Other, a project note) happens in editorkit's Composer,
shown as a sheet over Anvil's own page, so it stays wherever Anvil is: the
console after a run. Its send button finishes; ↩ in the header closes it
and keeps the draft.

The arrival (verdict pop, growing bars) plays once: ARRIVAL_SECONDS after a
run lands the page is redrawn without it, because a resize builds a fresh
web view that would otherwise play it again.

Rules (library/guides/editorkit-windows.md): card kit only, the clipboard
through editorkit.clip, never ui.delay (timed work runs on the window's
clock), state kept on this object.
"""
import os
import time

import editorkit as ek
from editorkit import clip
from editorkit.web import tiles

from . import items as run_items
from . import page as run_page
from . import projects as project_data
from . import projects_page
from . import history as run_history
from . import runs_page
from . import toolbox_entry


# --- Settings ---------------------------------------------------------------

TITLE = 'Anvil'
EMOJI = '🔨'
WINDOW_KEY = 'anvil'
FIRST_SIZE = (360, 520)
GONE_PLACES = ('hidden', 'closed')       # Window.place values with nothing on screen
AUTO_OPEN_SECONDS = 1.2                  # the landing shows first, then a lone OPEN opens
ARRIVAL_SECONDS = 1.0                    # then the page is redrawn without its arrival
TOOLBOX_ICON = '🧰'

TYPING_CANCEL_ICON = '↩'
TYPING_SPELLCHECK = True                 # spellcheck and autocorrect start on



def say(words):
    """A short heads-up message; silent where the console module is missing."""
    try:
        import console
        console.hud_alert(words)
    except Exception:
        pass


def show_page(board, page, keep_scroll):
    """board.show(page), keeping the scroll position when asked. Falls back
    to a plain show (back to the top) on an editorkit without keep_scroll."""
    try:
        board.show(page, keep_scroll=keep_scroll)
    except TypeError:
        board.show(page)


class Landing(object):
    """The Anvil window and the run it is showing."""

    def __init__(self):
        self.window = None
        self.board = None                # the Run page's tile
        self.projects_board = None       # the Projects page's tile
        self.runs_board = None           # the Runs page's tile
        self.recent_runs = []            # history.recent() summaries for the Runs page
        self.opener = None
        self.model = None
        self.items = []                  # what the bundle asked for (items.py)
        self.answers = {}                # answers so far, by item number
        self.unfolded = set()            # see page.py: sections flipped from their default
        self.arriving = False            # the next draw is a run's first: play the arrival
        self.settle_due = None           # when to redraw without the arrival
        self.open_due = None             # (time, item): a lone OPEN waiting to open
        self.projects = []               # registered projects (projects.py)
        self.chosen_project = None       # id shown on the Projects page; None: the list
        self.typing = None               # (TextBox, on_done) while a text sheet is open
        self.live = None                 # Forge's LiveRun while a run is going
        self.live_version = None         # the LiveRun version last drawn

    # Showing a run
    def show_run(self, model, items=()):
        self.live = None
        self.model = model
        self.items = list(items)
        self.answers = run_items.load_answers(model.stamp) if self.items else {}
        self.unfolded = set()
        self.arriving = True
        if self.window is None or self.window.place in GONE_PLACES:
            self.build_window()
            self.draw(keep_scroll=False)
            self.land()
        else:
            self.draw(keep_scroll=False)
            self.window.show()
        self.settle_due = time.time() + ARRIVAL_SECONDS
        self.plan_auto_open()
        self.refresh_projects()
        self.refresh_runs()
        toolbox_entry.ensure()

    # A run still going
    def start_live(self, live):
        """A run has started: show its live page, filled in from live
        (Forge's LiveRun, plain data behind a lock) on the window's clock,
        until show_run replaces it with the finished run."""
        self.live = live
        self.live_version = None
        self.open_due = None
        self.settle_due = None
        if self.typing is not None:
            self.close_typing()
        if self.window is None or self.window.place in GONE_PLACES:
            self.build_window()
            self.draw_live(keep_scroll=False)
            self.land()
        else:
            self.draw_live(keep_scroll=False)
            self.window.show()

    def follow_live(self):
        if self.live.snapshot()['version'] != self.live_version:
            self.draw_live()

    def draw_live(self, keep_scroll=True):
        snapshot = self.live.snapshot()
        self.live_version = snapshot['version']
        show_page(self.board, run_page.build_live_page(snapshot), keep_scroll)

    def step_aside(self):
        """Fold away so the built-in landing can show a run's console output."""
        self.live = None
        if self.window is not None and self.window.place not in GONE_PLACES:
            self.window.minimise()

    def build_window(self):
        self.window = ek.Window(TITLE, emoji=EMOJI, key=WINDOW_KEY, size=FIRST_SIZE)
        self.board = tiles.Cards(self.window, on_pick=self.picked, zoom_key=WINDOW_KEY,
                                 extra_css=run_page.tile_css())
        self.window.add_page('Run', self.board)
        self.runs_board = tiles.Cards(self.window, on_pick=self.picked,
                                      zoom_key=WINDOW_KEY + '-runs',
                                      extra_css=run_page.tile_css())
        self.window.add_page('Runs', self.runs_board)
        if project_data.available(self.workspace()):   # only with PROJECTS' catalogue
            self.projects_board = tiles.Cards(self.window, on_pick=self.picked,
                                              zoom_key=WINDOW_KEY + '-projects',
                                              extra_css=run_page.tile_css())
            self.window.add_page('Projects', self.projects_board)
        try:
            self.window.set_page('Run')
        except Exception:
            pass
        self.window.add_button(TOOLBOX_ICON, self.open_toolbox, name='toolbox')
        self.opener = ek.Opener(self.window)
        self.window.every(self.tick)

    def draw(self, keep_scroll=True):
        """Redraw the run page. A new run passes keep_scroll=False and starts
        at the top; taps keep the page where it was."""
        show_page(self.board, run_page.build_page(self.model, self.unfolded,
                                                  arriving=self.arriving,
                                                  items=self.items, answers=self.answers,
                                                  history=self.history_around()),
                  keep_scroll)
        self.arriving = False

    def land(self):
        """A new window goes to the console when it can, else over the code."""
        if self.window.can_use_console():
            self.window.to_console()
        if self.window.place in GONE_PLACES:
            self.window.show()

    # A lone OPEN opens by itself
    def plan_auto_open(self):
        """One OPEN in the bundle opens after the landing shows, as long as
        nothing is waiting for an answer: opening a file puts the console,
        and Anvil with it, away. Several OPENs, or one beside questions and
        checks, stay as rows to tap. A skipped OPEN never opens."""
        wanted = [item for item in self.items
                  if item.get('kind') == 'open' and not item.get('skipped')]
        self.open_due = None
        if len(wanted) == 1 and not run_items.answerable(self.items):
            self.open_due = (time.time() + AUTO_OPEN_SECONDS, wanted[0])

    def tick(self, now=None):
        """The window's clock: follows a live run, settles the arrival, then
        opens a lone OPEN when it is due."""
        if self.live is not None:
            self.follow_live()
        if self.settle_due is not None and time.time() >= self.settle_due:
            self.settle_due = None
            self.draw()
        if self.open_due is None or time.time() < self.open_due[0]:
            return
        item = self.open_due[1]
        self.open_due = None
        try:
            import console
            console.hide_output()
        except Exception:
            pass
        self.open_file(item['path'], item.get('target_line'))

    # Taps
    def picked(self, item):
        if not isinstance(item, tuple) or not item:
            return
        action = item[0]
        if action == 'fold':
            self.unfolded ^= {item[1]}
            self.draw()
        elif action == 'copy_packet':
            self.copy(self.model.packet, 'Packet copied', 'No packet stored for this run')
        elif action == 'copy_reply':
            self.copy_reply()
        elif action == 'copy_diff':
            self.copy('ENV: pythonista\nDIFF %s' % self.model.stamp, 'DIFF bundle copied')
        elif action == 'last_edit':
            row = self.model.last_edit()
            if row is None:
                say('No file in this run')
            else:
                self.open_file(row.path, row.start_line)
        elif action == 'open':
            self.open_file(item[1], item[2])
        elif action == 'answer':
            self.set_answer(item[1], item[2])
        elif action == 'answer_other':
            self.ask_other(item[1])
        elif action == 'check':
            self.toggle_check(item[1])
        elif action == 'project':
            self.chosen_project = item[1]
            self.draw_projects()
        elif action == 'projects_back':
            self.chosen_project = None
            self.draw_projects()
        elif action == 'add_note':
            self.ask_note(item[1])
        elif action == 'history':
            self.show_stored(item[1])
        elif action == 'runs_refresh':
            self.refresh_runs()
        elif action == 'copy_revert':
            self.copy('ENV: pythonista\nREVERT %s\n' % self.model.stamp,
                      'REVERT bundle copied: run Forge to undo %s' % self.model.stamp)
        elif action == 'copy_carry_on':
            command = run_page.carry_on_command(self.model)
            self.copy(command and 'ENV: pythonista\n%s\n' % command,
                      'Bundle copied: run Forge to carry on', 'Nothing to carry on')

    def copy(self, text, done, nothing='Nothing to copy'):
        if not text:
            say(nothing)
            return
        clip.set_text(text)
        say(done)

    def copy_reply(self):
        if not self.model.packet:
            say('No packet stored for this run')
            return
        reply = run_items.reply_text(self.model.stamp, self.items, self.answers)
        self.copy(self.model.packet.rstrip('\n') + '\n\n' + reply + '\n',
                  'Packet with reply copied')

    def open_file(self, path, line):
        full_path = os.path.join(self.model.project_root, path)
        if not os.path.isfile(full_path):
            say('File is no longer there')
            return
        self.opener.go(full_path, line or 1)

    def open_toolbox(self, *ignored):
        try:
            from editorkit_toolbox import hub
            hub.open_hub()
        except Exception as error:
            say('Toolbox did not open: %s' % error)

    # Answers
    def answer_value(self, number):
        return (self.answers.get(str(number)) or {}).get('value')

    def set_answer(self, number, value):
        """Record an answer, save it beside the run at once, and redraw."""
        self.answers[str(number)] = {'value': value}
        run_items.save_answers(self.model.stamp, self.answers)
        self.draw()

    def toggle_check(self, number):
        self.set_answer(number, not self.answer_value(number))

    def ask_other(self, number):
        """A typed answer, in the composer, with the question quoted above."""
        current = self.answer_value(number)
        item = next((item for item in self.items
                     if str(item.get('number')) == str(number)), {})
        self.type_text('Your answer', lambda text: self.set_answer(number, text),
                       placeholder='Your answer…', context=item.get('text'),
                       text=current if isinstance(current, str) else '',
                       draft_key='anvil-%s-%s' % (self.model.stamp, number))

    # Projects
    def workspace(self):
        return getattr(self.model, 'project_root', None) or project_data.DEFAULT_WORKSPACE

    def refresh_projects(self):
        """Reload the catalogue and redraw the Projects page. A projects
        problem never stops a run from showing."""
        try:
            self.projects = project_data.load_projects(self.workspace())
            self.draw_projects()
        except Exception as error:
            print('[anvil] projects page unavailable: %s' % error)

    def draw_projects(self, keep_scroll=False):
        """The list, or the chosen project. Moving between them starts at the
        top; a redraw of the same view (a saved note) keeps the scroll."""
        if self.projects_board is None:
            return                       # no Projects page here (no catalogue)
        project = project_data.find_project(self.projects, self.chosen_project)
        if project is None:
            self.chosen_project = None
            page = projects_page.build_list(self.projects)
        else:
            notes = project_data.notes_for(project['id'], self.workspace())
            page = projects_page.build_detail(project, notes)
        show_page(self.projects_board, page, keep_scroll)

    # Run history (history.py, runs_page.py)
    def history_around(self):
        """(older stamp, newer stamp) around the run shown; never stops a draw."""
        try:
            return run_history.neighbours(self.model.stamp)
        except Exception:
            return (None, None)

    def show_stored(self, stamp):
        """Show a run from Forge's history. No arrival and no auto-open:
        this is looking back. A run that will not load says so."""
        try:
            model, items = run_history.load_model(stamp)
        except Exception as error:
            say('Run %s did not load: %s' % (stamp, error))
            return
        self.live = None
        self.model = model
        self.items = list(items)
        self.answers = run_items.load_answers(model.stamp) if self.items else {}
        self.unfolded = set()
        self.arriving = False
        self.open_due = None
        self.draw(keep_scroll=False)
        self.draw_runs(keep_scroll=True)
        try:
            self.window.set_page('Run')
        except Exception:
            pass

    def refresh_runs(self):
        """Reread Forge's recent runs and redraw the Runs page. A history
        problem never stops a run from showing."""
        try:
            self.recent_runs = run_history.recent()
            self.draw_runs()
        except Exception as error:
            print('[anvil] runs page unavailable: %s' % error)

    def draw_runs(self, keep_scroll=False):
        if self.runs_board is None:
            return
        current = self.model.stamp if self.model is not None else None
        show_page(self.runs_board, runs_page.build_runs(self.recent_runs, current), keep_scroll)

    def ask_note(self, project_id):
        project = project_data.find_project(self.projects, project_id)
        if project is None:
            say('Project not found')
            return
        title = project.get('title') or project_id

        def save(text):
            try:
                project_data.add_note(project, text, self.workspace())
            except Exception as error:
                say('Note not saved: %s' % error)
                return
            say('Note saved')
            self.draw_projects(keep_scroll=True)

        self.type_text('Note', save, placeholder='Write a note…',
                       context='Note on %s' % title,
                       draft_key='anvil-note-%s' % project_id)

    # Typing in a sheet over Anvil
    def type_text(self, title, on_done, placeholder='Write…', context=None,
                  text='', draft_key=None):
        """Open editorkit's Composer as a sheet over Anvil's page, where Anvil
        is (the console after a run). Its send button hands the text to
        on_done(text); ↩ in the header closes it, keeping the draft."""
        from editorkit.native.composer import Composer, ComposerSheet
        if self.typing is not None:
            self.close_typing()
        composer = Composer(self.window, text, placeholder=placeholder, context=context,
                            on_send=self.sent, draft_key=draft_key,
                            spellcheck=TYPING_SPELLCHECK)
        self.typing = (composer, on_done)
        self.window.show_sheet(ComposerSheet(composer))
        self.window.add_button(TYPING_CANCEL_ICON, self.cancel_typing, name='typing_cancel')
        self.window.set_title(title)
        self.window.when_still(lambda window: window.focus(composer.text_view))

    def sent(self, text):
        """The composer's send: close the sheet, then hand on the text."""
        if self.typing is None:
            return
        composer, on_done = self.typing
        self.close_typing()
        on_done(text)

    def cancel_typing(self, *ignored):
        if self.typing is not None:
            self.close_typing()

    def close_typing(self):
        composer, on_done = self.typing
        self.typing = None
        try:
            composer.text_view.end_editing()
        except Exception:
            pass
        self.window.close_sheet()
        self.window.remove_button('typing_cancel')
        self.window.set_title(TITLE)


# One Landing for the session. The module lives in site-packages, so it and
# the window survive between Forge runs.
_landing = None


def show_run(model, items=()):
    """Show model's run, and what its bundle asked for, in Anvil. Returns True."""
    global _landing
    if _landing is None:
        _landing = Landing()
    _landing.show_run(model, items)
    return True


def start_live(live):
    """The live listener's dock call, at run start (Forge's thread, as
    show_run is called after the run). Returns True."""
    global _landing
    if _landing is None:
        _landing = Landing()
    _landing.start_live(live)
    return True


def step_aside():
    if _landing is not None:
        _landing.step_aside()
