# -*- coding: utf-8 -*-
"""Anvil's window: one editorkit window that shows a Forge run and acts on taps.

    from anvil import landing
    landing.show_run(model, items)     # model: Forge's LandingModel; items: items.py

One window (key 'anvil') is kept and reused: a new run redraws its page and
brings it forward. It lands over the console, where a run ends; if the
console cannot take it, it opens over the code.

Pages: Run (page.py), Help (help_page.py, read from Forge by help_data.py:
its ops, docs and the workspace's guides), Aliases (aliases_page.py; read,
checked and written straight to aliases.json by aliases_data.py) and
Projects (projects_page.py: the registered projects and notes left on
them). ◀ in the header goes back from the page opened last. 🕘 in the header swaps the Run page for
Forge's recent runs (runs_page.py, read by history.py); a tap on one shows
it, and ◀ ▶ on the run page step through them too. Toolbox (toolbox_page.py)
is the second tab when editorkit's Toolbox is installed: your tools in your
hub order, and recent scripts.

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
from . import help_data
from . import help_page
from . import aliases_data
from . import aliases_page
from . import runs_page
from . import toolbox_entry
from . import toolbox_page


# --- Settings ---------------------------------------------------------------

TITLE = 'Forge'
EMOJI = '🔨'
WINDOW_KEY = 'anvil'
FIRST_SIZE = (360, 520)
GONE_PLACES = ('hidden', 'closed')       # Window.place values with nothing on screen
AUTO_OPEN_SECONDS = 1.2                  # the landing shows first, then a lone OPEN opens
ARRIVAL_SECONDS = 1.0                    # then the page is redrawn without its arrival

HISTORY_ICON = '🕘'
HELP_BACK_ICON = '◀'

TYPING_CANCEL_ICON = '↩'
AUTOSAVE_SECONDS = 2.0                   # notes are saved this often while typing
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
        self.toolbox_board = None        # the Toolbox page's tile (only with Toolbox installed)
        self.toolbox_group = None        # the group shown on the Toolbox page; None: every tool
        self.showing_history = False     # 🕘 is on: the Run page lists recent runs
        self.help_board = None           # the Help page's tile
        self.help_view = None            # None: the list; ('op', name) or ('doc', kind, name)
        self.aliases_board = None        # the Aliases page's tile
        self.alias_view = None           # None: the list; else the alias shown
        self.alias_removing = None       # the alias whose 🗑 was tapped once
        self.aliases_path = None         # aliases.json, found once (aliases_data.aliases_path)
        self.opened_tabs = []            # tabs with a page open, oldest first: ◀ goes back from the last
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
        self.answers = run_items.load_answers(model.stamp)
        self.unfolded = set()
        self.arriving = True
        self.showing_history = False
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
        self.draw_toolbox()
        toolbox_entry.ensure()

    # A run still going
    def start_live(self, live):
        """A run has started: show its live page, filled in from live
        (Forge's LiveRun, plain data behind a lock) on the window's clock,
        until show_run replaces it with the finished run."""
        self.live = live
        self.live_version = None
        self.showing_history = False
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
        if self.showing_history:
            return                       # the run list is up; ◀ Back to run draws the live run
        if self.live.snapshot()['version'] != self.live_version:
            self.draw_live()
        else:
            self.start_clock()      # cheap and guarded: in case a reload lost it

    def draw_live(self, keep_scroll=True):
        snapshot = self.live.snapshot()
        self.live_version = snapshot['version']
        show_page(self.board, run_page.build_live_page(snapshot, self.active_seconds(snapshot)),
                  keep_scroll)
        self.start_clock()

    def active_seconds(self, snapshot):
        """How long the active op has run, timed from when Anvil first saw it
        (its stamp, index and op name together say which op it is)."""
        active = snapshot.get('active')
        if not active:
            self.active_key = None
            return 0.0
        key = (snapshot.get('stamp'), active.get('index'), active.get('op'))
        if key != getattr(self, 'active_key', None):
            self.active_key = key
            self.active_since = time.time()
        return time.time() - self.active_since

    def start_clock(self):
        """Let the page tick the running op's clock itself."""
        try:
            self.board.run(run_page.CLOCK_SCRIPT)
        except Exception:
            pass

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
        if toolbox_page.available():
            self.toolbox_board = tiles.Cards(self.window, on_pick=self.toolbox_picked,
                                             zoom_key=WINDOW_KEY + '-toolbox',
                                             extra_css=toolbox_page.css())
            self.window.add_page('Toolbox', self.toolbox_board)
        self.help_board = tiles.Cards(self.window, on_pick=self.picked,
                                      zoom_key=WINDOW_KEY + '-help',
                                      extra_css=run_page.tile_css() + help_page.CSS)
        self.window.add_page('Help', self.help_board)
        self.aliases_board = tiles.Cards(self.window, on_pick=self.picked,
                                         zoom_key=WINDOW_KEY + '-aliases',
                                         extra_css=(run_page.tile_css() + help_page.CSS
                                                    + aliases_page.CSS))
        self.window.add_page('Aliases', self.aliases_board)

        if project_data.available(self.workspace()):   # only with PROJECTS' catalogue
            self.projects_board = tiles.Cards(self.window, on_pick=self.picked,
                                              zoom_key=WINDOW_KEY + '-projects',
                                              extra_css=run_page.tile_css())
            self.window.add_page('Projects', self.projects_board)
        try:
            self.window.set_page('Run')
        except Exception:
            pass

        self.window.add_button(HISTORY_ICON, self.toggle_history, name='history')
        self.opener = ek.Opener(self.window)
        self.window.every(self.tick)
        self.draw_help()
        self.draw_aliases()
        self.draw_toolbox()

    def draw(self, keep_scroll=True):
        """Redraw the Run page: the run list while 🕘 is on, the live run
        while one is going, else the run. A new run passes keep_scroll=False
        and starts at the top; taps keep the page where it was."""
        self.show_history_button()
        if self.showing_history:
            current = self.model.stamp if self.model is not None else None
            show_page(self.board, runs_page.build_runs(self.recent_runs, current), keep_scroll)
            return
        if self.live is not None:
            self.draw_live(keep_scroll)
            return
        if self.model is None:
            return
        show_page(self.board, run_page.build_page(self.model, self.unfolded,
                                                  arriving=self.arriving,
                                                  items=self.items, answers=self.answers,
                                                  history=self.history_around()),
                  keep_scroll)
        self.arriving = False

    def show_history_button(self):
        """🕘 lit while the run list is showing."""
        try:
            self.window.set_button('history', on=self.showing_history)
        except Exception:
            pass

    def toggle_history(self, *ignored):
        """🕘 and ◀ Back to run: swap the Run page between the run and
        Forge's recent runs, starting at the top."""
        self.showing_history = not self.showing_history
        if self.showing_history:
            self.load_recent_runs()
        try:
            self.window.set_page('Run')
        except Exception:
            pass
        self.draw(keep_scroll=False)

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
        """The window's clock: saves text being typed that asked for it,
        follows a live run, settles the arrival, then opens a lone OPEN
        when it is due."""
        self.autosave_typing()
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
        elif action == 'notes':
            self.edit_notes()
        elif action == 'copy_diff':
            self.copy('ENV: pythonista\nDIFF %s' % self.model.stamp, 'DIFF bundle copied')
        elif action == 'run_forge':
            from . import run_forge
            run_forge.run_clipboard_bundle(say)

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
        elif action == 'history_close':
            self.toggle_history()
        elif action == 'help_op':
            self.help_view = ('op', item[1])
            self.note_opened('Help')
            self.draw_help()
        elif action == 'help_doc':
            self.help_view = ('doc', item[1], item[2])
            self.note_opened('Help')
            self.draw_help()
        elif action == 'help_back':
            self.close_help()
        elif action == 'alias':
            self.open_alias(item[1])
        elif action == 'alias_new':
            self.new_alias()
        elif action == 'alias_field':
            self.edit_alias_field(item[1], item[2])
        elif action == 'alias_copy':
            self.copy(item[1], 'Copied "%s": run Forge with it' % item[1])
        elif action == 'alias_args':
            self.ask_alias_args(item[1])
        elif action == 'alias_remove':
            self.remove_alias(item[1])
        elif action == 'aliases_refresh':
            self.draw_aliases(keep_scroll=True)
        elif action == 'alias_back':
            self.close_alias()
        elif action == 'copy_text':
            self.copy(item[1], item[2])
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

    # Toolbox tab
    def draw_toolbox(self):
        """Redraw the Toolbox page (recent scripts change between runs). A
        Toolbox problem never stops a run from showing."""
        if self.toolbox_board is None:
            return
        try:
            self.toolbox_board.show(toolbox_page.build_page(self.toolbox_group))
        except Exception as error:
            print('[anvil] toolbox page unavailable: %s' % error)

    def toolbox_picked(self, item):
        """A tap on the Toolbox page: a tool opens its own window, a group
        shows its tools, a recent script opens (📜: in a script window).
        Anything else (ℹ️ About, ⚙️ Settings) opens the hub itself."""
        try:
            from editorkit_toolbox import search
            if isinstance(item, search.ViewHit):
                from editorkit_toolbox import scriptview
                scriptview.open_script_window(item.hit.path, item.hit.line)
                self.reveal_editor()
                return
            kind, thing = item
            if kind in ('group', 'back'):
                self.toolbox_group = thing if kind == 'group' else None
                self.draw_toolbox()
            elif kind == 'file':
                ek.open_file(thing)
                self.reveal_editor()
            elif kind == 'tool' and thing.get('open') is not None:
                thing['open']()
                self.reveal_editor()
            elif kind == 'tool':
                say('%s could not load: see it in the Toolbox hub' % thing['name'])
            else:
                self.open_toolbox()
        except Exception as error:
            say('Toolbox: %s' % error)

    def reveal_editor(self):
        """Slide the console away, so what just opened over the code shows
        while Anvil stays in the console. Never raises."""
        try:
            from editorkit_toolbox import scriptops
            scriptops.bring_editor_forward()
        except Exception:
            pass

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

    # Help (help_data.py, help_page.py)
    def draw_help(self, keep_scroll=False):
        """The list of ops, docs and guides, or the one chosen. Read from
        Forge each time, so it matches the Forge that is running. A help
        problem never stops a run from showing."""
        if self.help_board is None:
            return
        try:
            page = self.help_page()
        except Exception as error:
            print('[anvil] help page unavailable: %s' % error)
            return
        show_page(self.help_board, page, keep_scroll)
        self.show_back_button()

    def help_page(self):
        view = self.help_view
        if view and view[0] == 'op':
            op = help_data.op_help(view[1])
            if op is not None:
                return help_page.build_op(op)
        elif view and view[0] == 'doc':
            doc = help_data.find_doc(view[1], view[2], self.workspace())
            if doc is not None:
                return help_page.build_doc(doc, help_data.doc_text(doc))
        self.help_view = None
        return help_page.build_list(help_data.ops(), help_data.docs(),
                                    help_data.guides(self.workspace()))

    # ◀: back from a Help or Aliases page
    def note_opened(self, tab):
        if tab in self.opened_tabs:
            self.opened_tabs.remove(tab)
        self.opened_tabs.append(tab)

    def tab_has_page_open(self, tab):
        return bool(self.help_view if tab == 'Help' else self.alias_view)

    def show_back_button(self):
        """◀ in the header while a Help or Aliases page is open."""
        try:
            self.window.remove_button('help_back')
        except Exception:
            pass
        if self.help_view or self.alias_view:
            self.window.add_button(HELP_BACK_ICON, self.go_back, name='help_back')

    def go_back(self, *ignored):
        """◀: back to the list of the tab whose page opened last, from
        whichever tab is showing."""
        open_tabs = [tab for tab in self.opened_tabs if self.tab_has_page_open(tab)]
        if not open_tabs:
            open_tabs = [tab for tab in ('Help', 'Aliases') if self.tab_has_page_open(tab)]
        if not open_tabs:
            self.show_back_button()
            return
        tab = open_tabs.pop()
        self.opened_tabs = open_tabs
        if tab == 'Help':
            self.help_view = None
            self.draw_help()
        else:
            self.alias_view = None
            self.alias_removing = None
            self.draw_aliases()
        try:
            self.window.set_page(tab)
        except Exception:
            pass

    # Aliases (aliases_data.py, aliases_page.py)
    def aliases_file(self):
        if self.aliases_path is None:
            self.aliases_path = aliases_data.aliases_path(run_history.runs_folder())
        return self.aliases_path

    def draw_aliases(self, keep_scroll=False):
        """The aliases by tag, or the one chosen, read fresh from
        aliases.json. An aliases problem never stops a run from showing."""
        if self.aliases_board is None:
            return
        try:
            aliases = aliases_data.load(self.aliases_file())
            entry = aliases.get(self.alias_view) if self.alias_view else None
            if entry is None:
                self.alias_view = None
                self.alias_removing = None
                page = aliases_page.build_list(aliases)
            else:
                page = aliases_page.build_detail(self.alias_view, entry,
                                                 removing=self.alias_removing == self.alias_view)
        except Exception as error:
            print('[anvil] aliases page unavailable: %s' % error)
            say('Aliases: %s' % error)
            return
        show_page(self.aliases_board, page, keep_scroll)
        self.show_back_button()

    def close_help(self):
        """◀ Help on the page: back to the list."""
        self.help_view = None
        if 'Help' in self.opened_tabs:
            self.opened_tabs.remove('Help')
        self.draw_help()

    def close_alias(self):
        """◀ Aliases on the page: back to the list."""
        self.alias_view = None
        self.alias_removing = None
        if 'Aliases' in self.opened_tabs:
            self.opened_tabs.remove('Aliases')
        self.draw_aliases()

    def open_alias(self, name):
        self.alias_view = name
        self.alias_removing = None
        self.note_opened('Aliases')
        self.draw_aliases()

    def op_names(self):
        """Forge's ops: an alias may not take one's name."""
        return help_data.forge_registry()[0]

    def write_alias(self, old_name, fields):
        """Straight to aliases.json (aliases_data keeps the backup)."""
        path = self.aliases_file()
        aliases_data.save(path, aliases_data.apply_edit(aliases_data.load(path), old_name, fields))

    # A new alias: its name, then its expansion; the rest on its page
    def new_alias(self, typed=''):
        self.type_text('New alias: name', self.new_alias_named, placeholder='name',
                       context=aliases_data.field_hint('name'), text=typed, spellcheck=False)

    def new_alias_named(self, typed):
        try:
            fields = aliases_data.with_field(aliases_data.blank_fields(), 'name', typed,
                                             self.op_names())
            if fields['name'] in aliases_data.load(self.aliases_file()):
                raise ValueError('There is already an alias called %s.' % fields['name'])
        except ValueError as error:
            say(str(error))
            self.new_alias(typed)
            return
        except Exception as error:
            say('Aliases: %s' % error)
            return
        self.ask_new_expansion(fields)

    def ask_new_expansion(self, fields, typed=''):
        self.type_text('New alias: %s' % fields['name'],
                       lambda text: self.save_new_alias(fields, text), placeholder='MAP .',
                       context=aliases_data.field_hint('expansion'), text=typed, spellcheck=False)

    def save_new_alias(self, fields, typed):
        try:
            fields = aliases_data.with_field(fields, 'expansion', typed)
            self.write_alias(None, fields)
        except ValueError as error:
            say(str(error))
            self.ask_new_expansion(fields, typed)
            return
        except Exception as error:
            say('Alias not saved: %s' % error)
            return
        say('Saved %s' % fields['name'])
        self.open_alias(fields['name'])

    # One field of an alias
    def edit_alias_field(self, name, field, typed=None):
        """The field in the composer, prefilled; typed: what was sent back
        after a problem."""
        try:
            entry = aliases_data.load(self.aliases_file()).get(name)
        except Exception as error:
            say('Aliases: %s' % error)
            return
        if entry is None:
            say('Alias %s is gone' % name)
            self.draw_aliases()
            return
        fields = aliases_data.fields_of(name, entry)
        text = aliases_data.field_text(fields, field) if typed is None else typed
        label = aliases_data.field_label(field)
        self.type_text('%s: %s' % (name, label),
                       lambda text: self.save_alias_field(name, field, text),
                       placeholder=label, context=aliases_data.field_hint(field),
                       text=text, spellcheck=field == 'description')

    def save_alias_field(self, name, field, typed):
        """Check the one field, then write. A problem says what is wrong
        and reopens the field as typed. A rename follows the alias."""
        try:
            entry = aliases_data.load(self.aliases_file()).get(name)
            if entry is None:
                raise ValueError('Alias %s is gone.' % name)
            fields = aliases_data.with_field(aliases_data.fields_of(name, entry), field, typed,
                                             self.op_names())
            self.write_alias(name, fields)
        except ValueError as error:
            say(str(error))
            self.edit_alias_field(name, field, typed)
            return
        except Exception as error:
            say('Alias not saved: %s' % error)
            return
        say('Saved %s' % aliases_data.field_label(field).lower())
        self.alias_view = fields['name']
        self.draw_aliases(keep_scroll=True)

    def ask_alias_args(self, name):
        """Fill in arguments…: ask for them, then copy 'name args'."""
        try:
            entry = aliases_data.load(self.aliases_file()).get(name) or {}
        except Exception:
            entry = {}

        def copy_line(typed):
            line = ('%s %s' % (name, ' '.join(typed.split()))).strip()
            self.copy(line, 'Copied "%s": run Forge with it' % line)

        self.type_text('Arguments', copy_line, placeholder='arguments…',
                       context=aliases_data.usage(name, entry), spellcheck=False)

    def remove_alias(self, name):
        """🗑 asks for a second tap; the second removes and saves."""
        if self.alias_removing != name:
            self.alias_removing = name
            self.draw_aliases(keep_scroll=True)
            return
        try:
            path = self.aliases_file()
            aliases = aliases_data.load(path)
            aliases.pop(name, None)
            aliases_data.save(path, aliases)
        except Exception as error:
            say('Not removed: %s' % error)
            return
        say('Removed %s' % name)
        self.alias_view = None
        self.alias_removing = None
        self.draw_aliases()

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
        self.answers = run_items.load_answers(model.stamp)
        self.unfolded = set()
        self.arriving = False
        self.open_due = None
        self.showing_history = False
        self.draw(keep_scroll=False)
        try:
            self.window.set_page('Run')
        except Exception:
            pass

    def refresh_runs(self):
        """Reread Forge's recent runs, and redraw them if they are showing."""
        if self.load_recent_runs() and self.showing_history:
            self.draw()

    def load_recent_runs(self):
        """history.recent() into self.recent_runs. A history problem never
        stops a run from showing: it prints and keeps the old list."""
        try:
            self.recent_runs = run_history.recent()
            return True
        except Exception as error:
            print('[anvil] run history unavailable: %s' % error)
            return False

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
    # Notes on a run (items.notes_of / with_notes, beside its answers)
    def edit_notes(self):
        """📝 Notes in the composer, prefilled; saved while typing, on send,
        and whenever the composer closes."""
        if self.model is None:
            return
        stamp = self.model.stamp

        def keep(text):
            self.save_notes(stamp, text)

        def finish(text):
            self.save_notes(stamp, text)
            say('Notes saved')
            self.draw(keep_scroll=True)

        self.type_text('Notes', finish, placeholder='Thoughts on this run…',
                       context='Notes on run %s: saved as you type, sent back by '
                               'Copy packet with reply.' % stamp,
                       text=run_items.notes_of(self.answers), autosave=keep)

    def save_notes(self, stamp, text):
        """Write the notes beside run stamp, only when they changed."""
        showing = self.model is not None and self.model.stamp == stamp
        answers = self.answers if showing else run_items.load_answers(stamp)
        updated = run_items.with_notes(answers, text)
        if updated == answers:
            return
        try:
            run_items.save_answers(stamp, updated)
        except Exception as error:
            print('[anvil] notes not saved: %s' % error)
            return
        if showing:
            self.answers = updated

    def typed_text(self, composer):
        try:
            return composer.text_view.text
        except Exception:
            return ''

    def autosave_typing(self):
        """Every AUTOSAVE_SECONDS, hand text being typed to its autosave."""
        if self.typing is None or self.typing[2] is None:
            return
        if time.time() < getattr(self, 'autosave_due', 0):
            return
        self.autosave_due = time.time() + AUTOSAVE_SECONDS
        try:
            self.typing[2](self.typed_text(self.typing[0]))
        except Exception as error:
            print('[anvil] autosave failed: %s' % error)

    def type_text(self, title, on_done, placeholder='Write…', context=None,
                  text='', draft_key=None, spellcheck=None, autosave=None):
        """Open editorkit's Composer as a sheet over Anvil's page, where Anvil
        is (the console after a run). Its send button hands the text to
        on_done(text); ↩ in the header closes it, keeping the draft.
        autosave(text), when given, is called every AUTOSAVE_SECONDS while
        typing and whenever the composer closes, however it closes."""
        from editorkit.native.composer import Composer, ComposerSheet
        if self.typing is not None:
            self.close_typing()
        composer = Composer(self.window, text, placeholder=placeholder, context=context,
                            on_send=self.sent, draft_key=draft_key,
                            spellcheck=TYPING_SPELLCHECK if spellcheck is None else spellcheck)
        self.typing = (composer, on_done, autosave)
        self.autosave_due = time.time() + AUTOSAVE_SECONDS
        self.window.show_sheet(ComposerSheet(composer))
        self.window.add_button(TYPING_CANCEL_ICON, self.cancel_typing, name='typing_cancel')
        self.window.set_title(title)
        self.window.when_still(lambda window: window.focus(composer.text_view))

    def sent(self, text):
        """The composer's send: close the sheet, then hand on the text."""
        if self.typing is None:
            return
        composer, on_done, autosave = self.typing
        self.close_typing()
        on_done(text)

    def cancel_typing(self, *ignored):
        if self.typing is not None:
            saves = self.typing[2] is not None
            self.close_typing()
            if saves:
                self.draw(keep_scroll=True)     # show what was kept

    def close_typing(self):
        composer, on_done, autosave = self.typing
        self.typing = None
        if autosave is not None:
            try:
                autosave(self.typed_text(composer))
            except Exception as error:
                print('[anvil] autosave failed: %s' % error)
        try:
            composer.text_view.end_editing()
        except Exception:
            pass
        self.window.close_sheet()
        self.window.remove_button('typing_cancel')
        self.window.set_title(TITLE)


# Which Anvil this is: tools/install.py writes installed_build.py into the
# installed copy, and tools/probe_loaded.py compares it with what the
# running session has loaded. A copy not installed that way (the source, or
# the Anvil bundled with Forge) says 'unstamped'.
try:
    from .installed_build import BUILD as ANVIL_BUILD
except ImportError:
    ANVIL_BUILD = 'unstamped'


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
