"""Anvil's run page: a finished Forge run as a card page.

Role: present · Part of: anvil/run_page · Pure

Pure: build_page turns Forge's LandingModel into an editorkit cards.Page and
touches no ui, so tests/smoke_page.py can check it headless.

    page = build_page(model)                  # as a run first shows
    page = build_page(model, {'ops'})         # with Operations toggled
    tiles.Cards(window, extra_css=CSS)        # the tile needs Anvil's CSS

Look (2026-11-22): words in the system font, colour only for status. A
clean run's verdict is one line; anything else is a card in its status
colour with the outcome bars. One filled button (Copy packet, or Copy
packet with reply when there is something to send back); history and
Revert sit in a quiet row. Menlo stays for ops, paths and stamps;
editorkit's code view for diffs and its docs look (prose) for output and
failures.

Top to bottom: verdict, buttons, failures, waiting for you, operations,
changed files, touched files (Toolbox file cards). Sections fold; unfolded
holds the names whose fold state the
user has flipped from its default:

    'ops'             Operations (default: open on a failed run or a look
                      run, folded on a clean run that changed files)
    ('file', path)    one changed file's diff (default: folded)
    ('op', number)    one operation's output (default: open on a look run,
                      one that changed nothing; else folded). Drawn by
                      renders.py where an op has a renderer.
    ('ask', number)   an answered question (default: folded to its answer)

Taps hand back the items below; landing.py acts on them.
"""
import os
import re

from editorkit.web import cards, codeview, prose

try:
    from editorkit.web import visuals
except Exception:                # older editorkit without visuals
    visuals = None

try:
    from editorkit_toolbox import filecards
except Exception:                # no Toolbox: the touched-files cards are left out
    filecards = None

from . import items as run_items
from . import renders

escape = cards.escape
Row = codeview.Row


# --- Settings ---------------------------------------------------------------

FORGE_PINK = '#E91E63'           # the double rule
FORGE_BLUE = '#5AA9FF'           # buttons, bars, fold marks
TONE_COLOURS = {'success': '#4CD964', 'warning': '#FFD166', 'danger': '#FF5A5F'}
TONE_WORDS = (('success', 'applied'), ('warning', 'skipped'), ('danger', 'failed'))
EDIT_OPS = ('WRITE', 'REPLACE', 'INSERT', 'DELETE')
LOOKED_AT_OPS = ('READ', 'RUN')  # touched files beyond the edited ones
MUTATING_OPS = EDIT_OPS + ('COPY', 'MOVE', 'REVERT', 'BRANCH')  # any of these: not a look run
LIVE_TONES = (('APPLIED', 'success'), ('SKIPPED', 'warning'), ('FAILED', 'danger'))
LIVE_GLYPHS = {'success': '✓', 'warning': '!', 'danger': '✗'}
LIVE_TARGET_CHARACTERS = 70
CARRY_ON_PREFIXES = ('Resume:', 'Repair:')
DIFF_LINES = 12                  # lines of one edit's old or new text shown
OUTPUT_LINES = 24                # lines of an operation's output when unfolded
SPACED_WORD_GAP = '   '
FOLDED, UNFOLDED = '▸', '▾'


# --- Items taps hand back ---------------------------------------------------

COPY_PACKET = ('copy_packet',)
COPY_DIFF = ('copy_diff',)
RUN_FORGE = ('run_forge',)             # run the bundle on the clipboard (run_forge.py)
COPY_REPLY = ('copy_reply',)
NOTES = ('notes',)                     # open the run's notes in the composer
COPY_REVERT = ('copy_revert',)       # copy a REVERT bundle for the run shown
COPY_CARRY_ON = ('copy_carry_on',)   # copy its FORGE resume / rerun bundle
CARRY_ON_COMMAND = re.compile(r'FORGE (resume|rerun) \S+')


def open_item(path, line):
    """Open path (project-relative) in the editor at line."""
    return ('open', path, line)


def fold_item(name):
    """Flip the fold state of the section called name."""
    return ('fold', name)


def answer_item(number, value):
    """Answer ASK item number with value (one of its options)."""
    return ('answer', number, value)


def other_item(number):
    """Type an answer to ASK item number."""
    return ('answer_other', number)


def check_item(number):
    """Tick or untick CHECK item number."""
    return ('check', number)


def history_item(stamp):
    """Show the stored run stamp (◀ ▶ and the Runs page)."""
    return ('history', stamp)


# --- Reading the model ------------------------------------------------------

def spaced(words):
    """'RUN CLEAN' -> 'R U N   C L E A N', Forge's banner style."""
    return SPACED_WORD_GAP.join(' '.join(word) for word in str(words).split())


def plural(count, word):
    return '%d %s%s' % (count, word, '' if count == 1 else 's')


def is_clean(model):
    return model.verdict[1] == 'success'


def is_look_run(model):
    """A run that changed nothing (reads, searches, maps, tests): its output
    is the point, so Operations and each op's output start open."""
    return bool(model.rows) and not any(row.op in MUTATING_OPS for row in model.rows)


def changed_files(model):
    """[(path, [rows])] for files this run edited, in first-edit order."""
    order, by_path = [], {}
    for row in model.rows:
        if row.path and row.op in EDIT_OPS and row.tone == 'success':
            if row.path not in by_path:
                by_path[row.path] = []
                order.append(row.path)
            by_path[row.path].append(row)
    return [(path, by_path[path]) for path in order]


def packet_section(packet, name):
    """The text under '=== NAME ===' in a packet, or ''."""
    lines, inside = [], False
    for line in str(packet or '').splitlines():
        if line.startswith('=== ') and line.rstrip().endswith('==='):
            if inside:
                break
            inside = line.strip() == '=== %s ===' % name
            continue
        if inside:
            lines.append(line)
    return '\n'.join(lines).strip('\n')


def carry_on_lines(model):
    """The packet's Resume: and Repair: lines, which say how to carry on."""
    return [line.strip() for line in model.packet.splitlines()
            if line.strip().startswith(CARRY_ON_PREFIXES)]


def carry_on_command(model):
    """The FORGE resume or rerun command in the packet's carry-on lines, or None."""
    for line in carry_on_lines(model):
        found = CARRY_ON_COMMAND.search(line)
        if found:
            return found.group(0)
    return None


def failure_blocks(failure_text):
    """The packet's FAILURE section as prose: each 'Op N · …' line a small
    heading, the rest read as Forge text ('Fix:' over its list, 'Help:' as
    a term)."""
    chunks, current = [], []
    for line in failure_text.splitlines():
        if line.startswith('Op ') and ' · ' in line and current:
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)
    blocks = []
    for chunk in chunks:
        blocks.append(prose.heading(chunk[0].strip(), 4))
        blocks.extend(renders.forge_text_blocks('\n'.join(chunk[1:])))
    return blocks


def carry_on_blocks(line):
    """A Resume: or Repair: line: its command alone in a block to copy, then
    the line's words with the command shown inline."""
    found = CARRY_ON_COMMAND.search(line)
    words = line.split(':', 1)[1].strip() if ':' in line else line
    if not found:
        return [prose.text(words)]
    command = found.group(0)
    return [prose.code(command, python=False),
            prose.text(words.replace(command, '`%s`' % command))]


def clipped(lines, limit):
    """(the first limit lines, how many were left out)."""
    return lines[:limit], max(len(lines) - limit, 0)


def edit_lines(row):
    """(removed lines, added lines) of one edit, from its parsed op."""
    blocks = row.parsed_op.get('blocks') or {}
    old_text = new_text = None
    for key, value in blocks.items():
        if 'OLD' in str(key).upper():
            old_text = str(value)
        if 'NEW' in str(key).upper():
            new_text = str(value)
    if row.op == 'REPLACE' and (old_text is not None or new_text is not None):
        return (old_text or '').splitlines(), (new_text or '').splitlines()
    body = str(row.parsed_op.get('body') or '')
    if body and row.op in ('WRITE', 'INSERT', 'REPLACE'):
        return [], body.splitlines()
    return [], []


def diff_rows(row):
    """One edit as code view rows: a heading, removed lines, then added
    lines numbered from where they landed."""
    removed, added = edit_lines(row)
    start = row.start_line or 1
    rows = [Row('%s  ·  line %d' % (row.op, start), 'heading')]
    if not removed and not added:
        rows.append(Row(row.message or row.status, 'note'))
        return rows
    shown, hidden = clipped(removed, DIFF_LINES)
    rows.extend(Row(line, 'remove') for line in shown)
    if hidden:
        rows.append(Row('… %s removed' % plural(hidden, 'more line'), 'note'))
    shown, hidden = clipped(added, DIFF_LINES)
    rows.extend(Row(line, 'add', number=start + index) for index, line in enumerate(shown))
    if hidden:
        rows.append(Row('… %s added' % plural(hidden, 'more line'), 'note'))
    return rows


# --- The sections -----------------------------------------------------------

def section_label(page, words, aside='', fold=None, is_open=False):
    """A small capital label; with fold (a section name) a tap flips it."""
    mark = ''
    if fold is not None:
        mark = '<span class="av-fold">%s</span>' % (UNFOLDED if is_open else FOLDED)
    page.parts.append('<div class="av-section"%s>%s%s<span class="av-aside">%s</span></div>'
                      % (page.go(fold_item(fold)) if fold is not None else '',
                         mark, escape(words), escape(aside)))


def button_html(page, label, item, kind='secondary'):
    """One button. kind 'primary' is the filled one: one per page section."""
    return '<div class="av-button %s"%s>%s</div>' % (kind, page.go(item), escape(label))


def outcomes_html(model):
    """Applied, skipped and failed as bars in their status colours."""
    biggest = max(max(model.counts.values()), 1)
    rows = []
    for tone, word in TONE_WORDS:
        count, colour = model.counts[tone], TONE_COLOURS[tone]
        rows.append(
            '<div class="av-outcome"><span class="av-name" style="color:%s">%s</span>'
            '<span class="av-track"><span class="av-fill" style="width:%d%%;background:%s">'
            '</span></span><span class="av-count">%d</span></div>'
            % (colour, word, round(100.0 * count / biggest), colour, count))
    return '<div class="av-outcomes">%s</div>' % ''.join(rows)


def add_banner(page, model):
    """The verdict. A clean run is one line; anything else is a card in its
    status colour with the outcome bars, so trouble is never just a line."""
    words, tone = model.verdict
    meta = [model.summary_line(), model.stamp or 'no stamp']
    mode = (model.mode or '').lower()
    if mode and mode != 'dev':
        meta.insert(0, mode.upper())
    meta_text = '  ·  '.join(meta)
    colour = TONE_COLOURS[tone]
    badge_html = (visuals.badge(words.upper(), colour=colour)
                  if visuals is not None and hasattr(visuals, 'badge') else '')
    stats_html = ''
    if visuals is not None and hasattr(visuals, 'stats'):
        elapsed_label = ('%.1fs' % model.run_elapsed
                         if getattr(model, 'run_elapsed', None) is not None else 'done')
        stats_html = visuals.stats([
            ('Ops', str(len(model.rows)), '', colour if is_clean(model) else None),
            ('Changed', str(len(changed_files(model))), '', None),
            ('Time', elapsed_label, '', None),
        ])
    if is_clean(model):
        page.parts.append(
            '<div class="av-verdict-line"><span class="av-verdict-mark" style="color:%s">✓</span>'
            '<span class="av-verdict-words">%s</span>%s<span class="av-meta">%s</span></div>'
            % (colour, escape(words.capitalize()), badge_html, escape(meta_text)))
        if stats_html:
            page.parts.append(stats_html)
        return
    page.parts.append(
        '<div class="av-verdict-card" style="--c:%s">'
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
        '<div class="av-verdict" style="color:%s">%s</div>%s</div>'
        '<div class="av-meta">%s</div>%s%s</div>'
        % (colour, colour, escape(words.capitalize()), badge_html,
           escape(meta_text), stats_html, outcomes_html(model)))


def add_outcomes(page, model):
    page.parts.append(outcomes_html(model))


def add_button_row(page, buttons, kind='secondary'):
    page.parts.append('<div class="av-buttons">%s</div>' % ''.join(
        button_html(page, label, item, kind) for label, item in buttons))


def add_buttons(page, model=None, history=None, reply=False):
    """The run's buttons, loudest first. One filled button: Copy packet, or
    Copy packet with reply when the bundle asked for something or notes are
    written. Then Run Forge, and Copy DIFF when files changed. Last, a quiet
    row of controls: step through Forge's run history (history=(older,
    newer) stamps), and copy a bundle that carries a failed run on or
    reverts this run. Controls only copy: the bundle is then run in Forge
    as usual."""
    primary = ('Copy packet with reply', COPY_REPLY) if reply else ('Copy packet', COPY_PACKET)
    add_button_row(page, (primary,), kind='primary')
    secondary = [('Copy packet', COPY_PACKET)] if reply else []
    secondary.append(('Run Forge', RUN_FORGE))
    if model is None or changed_files(model):
        secondary.append(('Copy DIFF', COPY_DIFF))
    add_button_row(page, secondary)
    if model is None:
        return
    older, newer = history or (None, None)
    controls = []
    if older:
        controls.append(('◀ Older', history_item(older)))
    if newer:
        controls.append(('Newer ▶', history_item(newer)))
    command = carry_on_command(model)
    if command:
        controls.append(('Copy %s' % command.split()[1], COPY_CARRY_ON))
    if model.touched_files:          # files this run itself changed; a resumed run's
        controls.append(('⟲ Revert', COPY_REVERT))   # earlier edits belong to the first run
    if controls:
        page.parts.append('<div class="av-controls">%s</div>' % ''.join(
            '<span class="av-control%s"%s>%s</span>'
            % (' danger' if item == COPY_REVERT else '', page.go(item), escape(label))
            for label, item in controls))


def add_failures(page, model):
    blocks = []
    failure_text = packet_section(model.packet, 'FAILURE')
    if failure_text:
        blocks.append(prose.callout('What went wrong', *failure_blocks(failure_text),
                                    kind='danger'))
    else:
        for row in model.rows:
            if row.tone == 'danger':
                blocks.append(prose.callout(
                    '%s  %s  %s' % (row.glyph, row.counter, row.op),
                    prose.text('%s: %s' % (row.status, row.message or 'no message')),
                    kind='danger'))
    for line in carry_on_lines(model):
        blocks.append(prose.callout('How to carry on', *carry_on_blocks(line), kind='warning'))
    if blocks:
        page.parts.append(prose.article(*blocks))


def waiting_html(page, item, answer, unfolded=()):
    """One requested item (an EDITOR OPEN, ASK, CHECK or NOTE) as a row,
    numbered as in the reply block. An answered ASK folds to its question
    and answer; a tap opens it again to change the answer."""
    kind, number = item['kind'], item['number']
    value = answer.get('value')
    number_html = '<span class="av-num">%s</span>' % number

    def line(text):
        return ('<div class="av-wait-line">%s<span class="av-wait-text">%s</span></div>'
                % (number_html, escape(text)))

    if kind == 'note':
        return '<div class="av-wait">%s</div>' % line(item['text'])

    if kind == 'ask' and item.get('skipped'):
        return ('<div class="av-wait">%s<div class="av-skipped">not asked: the run was not clean'
                ' \u2014 answer after the fix</div></div>' % line(item['text']))

    if kind == 'open':
        where = item['path']
        if item.get('target_line'):
            where += ':%d' % item['target_line']
        if item.get('skipped'):
            reason = 'file not found' if item.get('missing') else 'not opened: the run was not clean'
            return '<div class="av-wait">%s<div class="av-skipped">%s</div></div>' % (line(where), reason)
        return ('<div class="av-file">%s<span class="av-path">%s</span>'
                '<b class="av-open"%s>Open</b></div>'
                % (number_html, escape(where),
                   page.go(open_item(item['path'], item.get('target_line') or 1))))

    if kind == 'check':
        if item.get('skipped'):
            return ('<div class="av-wait">%s<div class="av-skipped">skipped: the run was not clean</div></div>'
                    % line(item['text']))
        return ('<div class="av-wait av-check%s"%s>%s<span class="av-box">%s</span>'
                '<span class="av-wait-text">%s</span></div>'
                % (' on' if value else '', page.go(check_item(number)), number_html,
                   '☑' if value else '☐', escape(item['text'])))

    fold = ('ask', number)
    options = list(item.get('options') or [])
    typed = bool(value) and value not in options
    status_badge = ''
    if value and visuals is not None and hasattr(visuals, 'badge'):
        badge_text = 'TYPED' if typed else 'ANSWERED'
        badge_col = FORGE_BLUE if typed else '#4CD964'
        status_badge = ' ' + visuals.badge(badge_text, colour=badge_col)

    if value and fold not in unfolded:
        return ('<div class="av-wait av-done"%s>%s<div class="av-answer">→ %s%s</div></div>'
                % (page.go(fold_item(fold)), line(item['text']), escape(str(value)), status_badge))

    choices = ''.join(
        '<div class="av-choice%s"%s>%s</div>'
        % (' on' if value == option else '', page.go(answer_item(number, option)),
           escape(option))
        for option in options)
    choices += ('<div class="av-choice%s"%s>Other…</div>'
                % (' on' if typed else '', page.go(other_item(number))))
    shown = ('<div class="av-typed">%s%s</div>' % (escape(str(value)), status_badge)
             if typed else '')
    return ('<div class="av-wait">%s<div class="av-choices">%s</div>%s</div>'
            % (line(item['text']), choices, shown))


def notes_html(page, notes):
    """📝 Notes: on every run, under what the bundle asked for. Shows what
    is written so far; a tap opens it to add more."""
    if notes:
        label = '📝 Notes · tap to add more'
        shown = '<div class="av-typed" style="white-space:pre-wrap">%s</div>' % escape(notes)
    else:
        label = '📝 Notes · tap to add your thoughts on this run'
        shown = ''
    return ('<div class="av-wait" style="cursor:pointer"%s><div class="av-wait-text">%s</div>%s</div>'
            % (page.go(NOTES), label, shown))


def add_waiting(page, items, answers, unfolded=()):
    """Waiting for you: what the bundle asked for, numbered as in the reply,
    then 📝 Notes (always), and the reply button once there is anything to
    send back. That button fills in when every question is answered."""
    answers = answers or {}
    to_answer = run_items.answerable(items) if items else []
    answered = run_items.answered_count(items, answers) if to_answer else 0
    if items:
        aside = '%d of %d answered' % (answered, len(to_answer)) if to_answer else ''
        section_label(page, 'WAITING FOR YOU', aside)
        if to_answer and visuals is not None and hasattr(visuals, 'meter'):
            all_done = answered == len(to_answer)
            meter_col = '#4CD964' if all_done else FORGE_BLUE
            page.parts.append(visuals.meter(answered, total=len(to_answer),
                                            label='Replies ready', colour=meter_col))
        page.parts.append(''.join(
            waiting_html(page, item, answers.get(str(item['number'])) or {}, unfolded)
            for item in items))
    notes = run_items.notes_of(answers)
    page.parts.append(notes_html(page, notes))
    if to_answer or notes:
        done = answered == len(to_answer)
        label = 'Copy packet with reply'
        if not done:
            label += ' · %d of %d' % (answered, len(to_answer))
        add_button_row(page, ((label, COPY_REPLY),), kind='primary' if done else 'secondary')


def add_changed(page, model, unfolded):
    files = changed_files(model)
    if not files:
        return
    section_label(page, 'CHANGED', plural(len(files), 'file'))
    for index, (path, rows) in enumerate(files):
        name = ('file', path)
        is_open = name in unfolded
        added = sum(len(edit_lines(row)[1]) for row in rows)
        removed = sum(len(edit_lines(row)[0]) for row in rows)
        line = rows[-1].start_line or 1
        page.parts.append(
            '<div class="av-file"%s><span class="av-fold">%s</span>'
            '<span class="av-path">%s</span><span class="av-plus">+%d</span>'
            '<span class="av-minus">−%d</span><b class="av-open"%s>Open</b></div>'
            % (page.go(fold_item(name)), UNFOLDED if is_open else FOLDED, escape(path),
               added, removed, page.go(open_item(path, line))))
        if is_open:
            found = []
            for row in rows:
                found.extend(diff_rows(row))
            page.parts.append(codeview.rows_section('av%d' % index, None, found)[0])


def touched_files(model):
    """(paths, edited): files the run edited, then ones it read or ran, that
    exist under the project root. edited is the set of edited paths."""
    edited = [path for path, rows in changed_files(model)]
    looked_at = []
    for row in model.rows:
        if row.path and row.op in LOOKED_AT_OPS and row.tone == 'success':
            path = row.path.split('::')[0]
            if path not in edited and path not in looked_at:
                looked_at.append(path)
    root = getattr(model, 'project_root', '') or ''
    paths = [path for path in edited + looked_at
             if root and os.path.isfile(os.path.join(root, path))]
    return paths, set(edited)


def add_touched(page, model):
    """Touched files as the Toolbox draws files (Home, Find): a card each.
    Without the Toolbox's file cards, slim rows: name, folder, a tag when
    edited; a tap opens the file either way."""
    paths, edited = touched_files(model)
    if not paths:
        return
    edited_count = len([path for path in paths if path in edited])
    read_or_run_count = len(paths) - edited_count
    section_label(page, 'TOUCHED', '%d edited · %d read or run'
                  % (edited_count, read_or_run_count))
    if visuals is not None and hasattr(visuals, 'stats') and len(paths) >= 2:
        page.parts.append(visuals.stats([
            ('Edited', str(edited_count), '', '#4CD964' if edited_count else None),
            ('Read/Run', str(read_or_run_count), '', FORGE_BLUE if read_or_run_count else None),
            ('Touched', str(len(paths)), '', None),
        ]))
    if filecards is not None:
        root = model.project_root
        page.grid([filecards.file_card(os.path.join(root, path), open_item(path, 1),
                                       where=os.path.dirname(path) or '.')
                   for path in paths], min_width=filecards.CARD_WIDTH)
        return
    rows = []
    for path in paths:
        tag = '<span class="av-tag">edited</span>' if path in edited else ''
        rows.append('<div class="av-touch"%s><span class="av-touch-name">%s</span>'
                    '<span class="av-touch-where">%s</span>%s</div>'
                    % (page.go(open_item(path, 1)), escape(os.path.basename(path)),
                       escape(os.path.dirname(path) or '.'), tag))
    page.parts.append('<div class="av-group">%s</div>' % ''.join(rows))


def plain_output_html(row):
    """An op's packet preview as prose code: what every op showed before
    renders, and what an op without a renderer still shows."""
    shown, hidden = clipped((row.preview or row.message or 'No output.').splitlines(),
                            OUTPUT_LINES)
    if hidden:
        shown.append('… %s' % plural(hidden, 'more line'))
    return prose.article(prose.code('\n'.join(shown), python=False))


def operation_html(page, row, slowest, unfolded, opened_by_default=False):
    name = ('op', row.number)
    colour = TONE_COLOURS[row.tone]
    status = ''
    if row.tone != 'success':
        status = ' <span class="av-status">%s</span>' % escape(row.status)
    bar = ''
    if row.seconds is not None:
        width = max(3, min(100, round(100.0 * row.seconds / max(slowest, 0.001))))
        bar = ('<span class="av-track"><span class="av-fill" style="width:%d%%"></span></span>'
               '<span class="av-secs">%.2fs</span>' % (width, row.seconds))
    detail = ''
    if (name in unfolded) != opened_by_default:
        context = renders.RenderContext(open_item, fold_item, unfolded)
        rendered = renders.detail_html(page, row, context)
        detail = '<div class="av-detail">%s</div>' % (rendered or plain_output_html(row))
    return ('<div class="av-op"%s><div class="av-op-top">'
            '<span class="av-glyph" style="color:%s">%s</span>'
            '<span class="av-counter">%s</span>'
            '<span class="av-opname" style="color:%s">%s%s</span>%s</div>'
            '<div class="av-target">%s</div>%s</div>'
            % (page.go(fold_item(name)), colour, escape(row.glyph), escape(row.counter),
               colour, escape(row.op), status, bar, escape(row.short_target(70)), detail))


def add_operations(page, model, unfolded):
    if not model.rows:
        return
    look = is_look_run(model)
    is_open = (look or not is_clean(model)) != ('ops' in unfolded)
    summary = ', '.join('%d %s' % (model.counts[tone], word)
                        for tone, word in TONE_WORDS if model.counts[tone])
    section_label(page, 'OPERATIONS', summary, fold='ops', is_open=is_open)
    if is_open:
        if visuals is not None and hasattr(visuals, 'steps') and len(model.rows) <= 16:
            pill_items = [('%d·%s' % (row.number, row.op), row.tone) for row in model.rows]
            page.parts.append(visuals.steps(pill_items))
        page.parts.append(''.join(operation_html(page, row, model.slowest, unfolded, look)
                                  for row in model.rows))


# --- The page ---------------------------------------------------------------

def build_page(model, unfolded=(), arriving=False, items=(), answers=None, history=None):
    """The whole run as one cards.Page.

    unfolded: see the module docstring. arriving=True plays the arrival
    (the verdict rises in, the bars grow); pass it only for a run's first
    draw, or every fold tap would replay it. items and answers (items.py)
    are what the bundle asked for and what has been answered so far.
    """
    unfolded = set(unfolded)
    items = list(items)
    answers = answers or {}
    reply = bool((run_items.answerable(items) if items else [])
                 or run_items.notes_of(answers))
    page = cards.Page()
    page.parts.append('<div class="av-page%s">' % (' av-arrive' if arriving else ''))
    add_banner(page, model)
    add_buttons(page, model, history, reply=reply)
    add_failures(page, model)
    add_waiting(page, items, answers, unfolded)
    add_operations(page, model, unfolded)
    add_changed(page, model, unfolded)
    add_touched(page, model)
    page.parts.append('</div>')
    return page


# --- The live page (a run still going) --------------------------------------

def live_tone(status):
    """'APPLIED' -> success, 'SKIPPED_…' -> warning, 'FAILED_…' -> danger."""
    for prefix, tone in LIVE_TONES:
        if str(status).upper().startswith(prefix):
            return tone
    return 'warning'


def short(text, limit=LIVE_TARGET_CHARACTERS):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1] + '…'


def live_row_html(number, entry, slowest):
    tone = live_tone(entry.get('status'))
    colour = TONE_COLOURS[tone]
    width = max(3, min(100, round(100.0 * entry['seconds'] / max(slowest, 0.001))))
    status = ''
    if tone != 'success':
        status = ' <span class="av-status">%s</span>' % escape(entry.get('status') or '')
    return ('<div class="av-op"><div class="av-op-top">'
            '<span class="av-glyph" style="color:%s">%s</span>'
            '<span class="av-counter">%d</span>'
            '<span class="av-opname" style="color:%s">%s%s</span>'
            '<span class="av-track"><span class="av-fill" style="width:%d%%"></span></span>'
            '<span class="av-secs">%.2fs</span></div>'
            '<div class="av-target">%s</div></div>'
            % (colour, LIVE_GLYPHS[tone], number, colour, escape(entry.get('op') or '?'),
               status, width, entry['seconds'], escape(short(entry.get('target')))))


def clock_text(seconds):
    """How long an op has run: 3.4s under a minute, then 1:05."""
    if seconds < 60:
        return '%.1fs' % seconds
    return '%d:%02d' % (seconds // 60, seconds % 60)


# The running op's clock ticks in the page itself, so it keeps counting
# while Python is busy with the op. Each drawn clock carries the seconds
# already run (data-base); a page that redraws picks up from there. Safe
# to run again: it starts one interval per page.
CLOCK_SCRIPT = """
if (!window.avClock) {
  window.avClock = setInterval(function () {
    var clock = document.getElementById('av-clock');
    if (!clock) return;
    if (!clock.dataset.t0)
      clock.dataset.t0 = Date.now() - parseFloat(clock.dataset.base || '0') * 1000;
    var s = (Date.now() - clock.dataset.t0) / 1000;
    var r = Math.floor(s % 60);
    clock.textContent = s < 60 ? s.toFixed(1) + 's'
                               : Math.floor(s / 60) + ':' + (r < 10 ? '0' : '') + r;
  }, 100);
}
"""


def active_row_html(number, active, seconds=0.0):
    """The op still running: its name, a pulse, and a clock counting up
    from seconds (CLOCK_SCRIPT keeps it ticking)."""
    return ('<div class="av-op av-running"><div class="av-op-top">'
            '<span class="av-glyph" style="color:var(--av-blue)">•</span>'
            '<span class="av-counter">%d</span>'
            '<span class="av-opname" style="color:var(--av-blue)">%s '
            '<span class="av-status">running…</span></span>'
            '<span class="av-secs" id="av-clock" data-base="%.2f">%s</span></div>'
            '<div class="av-target">%s</div></div>'
            % (number, escape(active.get('op') or '?'), seconds, clock_text(seconds),
               escape(short(active.get('target')))))


def build_live_page(snapshot, active_seconds=0.0):
    """A run still going, as one cards.Page, from Forge's live record
    (forge.adapters.pythonista.landing.live.LiveRun.snapshot(): stamp, mode,
    total, finished [{op, target, status, seconds}], active, done).
    active_seconds: how long the active op has run so far, for its clock."""
    finished = list(snapshot.get('finished') or [])
    active = snapshot.get('active')
    total = snapshot.get('total') or 0
    step = len(finished) + (1 if active else 0)
    where = 'op %d of %d' % (step, total) if total else 'starting'
    elapsed = sum(entry['seconds'] for entry in finished)
    summary = '%s  ·  %s  ·  %s  ·  %.1fs' % (str(snapshot.get('mode') or 'dev').upper(),
                                            snapshot.get('stamp') or 'no stamp', where, elapsed)
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    live_badge = (visuals.badge('LIVE', colour=FORGE_BLUE)
                  if visuals is not None and hasattr(visuals, 'badge') else '')
    page.parts.append(
        '<div class="av-banner"><div class="av-rule"></div>'
        '<div class="av-verdict" style="color:var(--av-blue)">%s %s</div>'
        '<div class="av-summary">%s</div><div class="av-rule"></div></div>'
        % (escape(spaced('RUNNING')), live_badge, escape(summary)))
    if visuals is not None and hasattr(visuals, 'stats'):
        page.parts.append(visuals.stats([
            ('Done', '%d/%d' % (len(finished), total) if total else str(len(finished)), '', FORGE_BLUE),
            ('Elapsed', '%.1fs' % elapsed, '', None),
            ('Active', active.get('op').upper() if active and active.get('op') else '—', '', FORGE_BLUE if active else None),
        ]))
    done_width = round(100.0 * len(finished) / total) if total else 0
    page.parts.append(
        '<div class="av-outcomes"><div class="av-outcome">'
        '<span class="av-name" style="color:var(--av-blue)">done</span>'
        '<span class="av-track"><span class="av-fill" style="width:%d%%"></span></span>'
        '<span class="av-count">%d</span></div></div>' % (done_width, len(finished)))
    section_label(page, 'OPERATIONS', '%d of %d' % (len(finished), total) if total else '')
    if visuals is not None and hasattr(visuals, 'steps'):
        step_pills = [(str(idx + 1) + '·' + str(entry.get('op') or '?').upper(),
                       live_tone(entry.get('status')))
                      for idx, entry in enumerate(finished)]
        if active:
            step_pills.append((str(step) + '·' + str(active.get('op') or '?').upper(), 'active'))
        if step_pills:
            page.parts.append(visuals.steps(step_pills))
    slowest = max([entry['seconds'] for entry in finished] + [0.001])
    rows = [live_row_html(index + 1, entry, slowest) for index, entry in enumerate(finished)]
    if active:
        rows.append(active_row_html(step, active, active_seconds))
    page.parts.append(''.join(rows))
    page.parts.append('</div>')
    return page


# --- The look ---------------------------------------------------------------
#
# Theme tokens (var(--text), --muted, --wash, --wash-strong, --rule) for
# everything; colour only says status (TONE_COLOURS) or "tap me" (Forge
# blue). Words in the system font; Menlo for ops, paths and stamps.

CSS = ':root { --av-blue: %s; }\n' % FORGE_BLUE + """
.av-verdict-line { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0 8px;
    padding: 10px 4px 2px; font: 16px/1.4 -apple-system, sans-serif; }
.av-verdict-mark { font-weight: 700; }
.av-verdict-words { font-weight: 600; }
.av-meta { font: 11px/1.5 Menlo, monospace; color: var(--muted); overflow-wrap: anywhere; }
.av-verdict-card { margin: 8px 2px 2px; padding: 10px 12px 8px; border-radius: 12px;
    background: var(--wash); box-shadow: inset 3px 0 0 var(--c, transparent); }
.av-verdict { font: 600 18px/1.3 -apple-system, sans-serif; }
.av-banner { text-align: center; }
.av-rule { border-top: 1px solid var(--rule); margin: 8px 2px; }
.av-summary { font: 11px/1.5 Menlo, monospace; color: var(--muted); padding: 2px 4px 0; }
.av-outcomes { padding: 8px 0 2px; }
.av-outcome { display: flex; align-items: center; font: 13px/1.7 -apple-system, sans-serif; }
.av-name { flex: 0 0 66px; }
.av-track { display: block; flex: 1 1 auto; height: 8px; border-radius: 4px;
    background: var(--wash-strong); overflow: hidden; }
.av-fill { display: block; height: 100%; border-radius: 4px; background: var(--av-blue); }
.av-count { flex: 0 0 30px; text-align: right; font-family: Menlo, monospace; }
.av-buttons { display: flex; padding: 8px 2px 0; }
.av-button { flex: 1 1 0; min-width: 0; margin: 0 4px; text-align: center; padding: 10px 4px;
    border-radius: 10px; font: 600 14px/1.2 -apple-system, sans-serif; cursor: pointer;
    color: var(--av-blue); background: var(--wash-strong); }
.av-button.primary { color: #0B1220; background: var(--av-blue); padding: 13px 4px; font-size: 16px; }
.av-controls { display: flex; flex-wrap: wrap; justify-content: center; gap: 2px 22px;
    padding: 10px 4px 0; font: 14px/1.4 -apple-system, sans-serif; }
.av-control { color: var(--muted); cursor: pointer; padding: 4px 2px; }
.av-control.danger { color: #FF5A5F; }
.av-section { font: 600 11px/1.4 -apple-system, sans-serif; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em; padding: 18px 4px 6px; }
.av-aside { font-weight: normal; margin-left: 10px; letter-spacing: 0; text-transform: none; }
.av-fold { display: inline-block; width: 1.3em; color: var(--av-blue); }
.av-file { display: flex; align-items: baseline; padding: 8px 4px;
    border-top: 1px solid var(--rule); font: 12px/1.4 Menlo, monospace; cursor: pointer; }
.av-path { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; padding-right: 8px; }
.av-plus { color: #4CD964; padding-right: 6px; }
.av-minus { color: #FF5A5F; padding-right: 10px; }
.av-open { flex: 0 0 auto; font: 600 13px -apple-system, sans-serif; color: var(--av-blue);
    background: var(--wash-strong); border-radius: 8px; padding: 4px 10px; }
.av-op { padding: 6px 4px 7px; border-top: 1px solid var(--rule); cursor: pointer; }
.av-op-top { display: flex; align-items: center; font: 13px/1.4 Menlo, monospace; }
.av-glyph { flex: 0 0 18px; font-weight: bold; }
.av-counter { flex: 0 0 48px; color: var(--muted); font-size: 11px; }
.av-opname { flex: 1 1 auto; min-width: 0; font-weight: bold; }
.av-status { font-weight: normal; font-size: 10px; }
.av-op .av-track { flex: 0 0 84px; height: 6px; }
.av-secs { flex: 0 0 48px; text-align: right; color: var(--muted); font-size: 11px; }
.av-target { font: 10px/1.4 Menlo, monospace; color: var(--muted); padding-left: 18px;
    overflow-wrap: anywhere; }
.av-detail { padding: 6px 0 0; }
@keyframes av-pop { from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: none; } }
@keyframes av-grow { from { width: 0; } }
.av-arrive .av-verdict-line, .av-arrive .av-verdict-card { animation: av-pop 0.3s ease-out; }
.av-arrive .av-fill { animation: av-grow 0.45s ease-out; }
.av-wait { padding: 11px 4px; border-top: 1px solid var(--rule);
    font: 15px/1.4 -apple-system, sans-serif; }
.av-wait-line { display: flex; align-items: baseline; }
.av-wait-text { flex: 1 1 auto; min-width: 0; overflow-wrap: anywhere; }
.av-num { flex: 0 0 24px; color: var(--muted); font: 600 13px/1.4 -apple-system, sans-serif; }
.av-choices { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 0 2px 24px; }
.av-choice { padding: 8px 15px; border-radius: 18px; background: var(--wash-strong);
    color: var(--text); font: 15px/1.2 -apple-system, sans-serif; cursor: pointer; }
.av-choice.on { background: var(--av-blue); color: #0B1220; font-weight: 600; }
.av-done { cursor: pointer; }
.av-answer { padding: 3px 0 0 24px; color: var(--muted); font-size: 14px; }
.av-check { display: flex; align-items: center; cursor: pointer; padding: 12px 4px; }
.av-box { flex: 0 0 34px; font-size: 24px; line-height: 1; color: var(--av-blue); }
.av-check.on .av-wait-text { opacity: 0.6; }
.av-skipped { color: var(--muted); font-size: 13px; padding: 3px 0 0 24px; }
.av-typed { color: var(--muted); font-size: 14px; padding: 4px 0 0 24px; }
.av-group { margin: 0 2px; border-radius: 12px; background: var(--wash); overflow: hidden; }
.av-touch { display: flex; align-items: baseline; gap: 8px; padding: 10px 12px;
    border-top: 1px solid var(--rule); cursor: pointer; font: 15px/1.3 -apple-system, sans-serif; }
.av-touch:first-child { border-top: none; }
.av-touch-name { font-weight: 600; }
.av-touch-where { flex: 1 1 auto; min-width: 0; color: var(--muted); font-size: 13px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.av-tag { font: 600 12px -apple-system, sans-serif; color: #4CD964; }
.av-muted { color: var(--muted); }
.av-project-title { font: 600 18px/1.3 -apple-system, sans-serif; padding: 10px 4px 4px; }
.av-field { padding: 6px 4px; font: 14px/1.4 -apple-system, sans-serif; }
.av-field-label { font: bold 10px/1.6 Menlo, monospace; color: var(--muted);
    letter-spacing: 0.04em; }
.av-note-date { font: 11px/1.5 Menlo, monospace; color: var(--muted); }
@keyframes av-pulse { 50% { opacity: 0.5; } }
.av-running { animation: av-pulse 1.2s ease-in-out infinite; }
"""


def tile_css():
    """CSS for a tile showing Anvil's pages: visuals, file cards, and Anvil's look."""
    vis_css = visuals.CSS if visuals is not None else ''
    cards_css = filecards.CSS if filecards is not None else ''
    return vis_css + cards_css + CSS