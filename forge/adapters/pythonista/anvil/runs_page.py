"""Anvil's Runs page: Forge's recent runs, newest first, one card each.

Role: present · Part of: anvil/runs · Pure

Pure: build_runs(summaries, current) turns history.recent() into a
cards.Page. A tap on a card hands back ('history', stamp); Refresh hands
back ('runs_refresh',); ◀ Back to run hands back ('history_close',). The
run Anvil is showing is outlined.
"""
from editorkit.web import cards

try:
    from editorkit.web import visuals
except Exception:
    visuals = None

from . import page as run_page

escape = cards.escape

CHANGED_SHOWN = 3            # changed files listed on a card before "+N more"
OP_NAMES_SHOWN = 6           # op names listed on a card
VERDICT_WORDS = {'success': 'Clean', 'warning': 'Partial', 'danger': 'Failed'}
REFRESH = ('runs_refresh',)
BACK_TO_RUN = ('history_close',)


def counts_words(counts):
    return ', '.join('%d %s' % (counts[tone], word)
                     for tone, word in run_page.TONE_WORDS if counts.get(tone))


def run_card(page, summary, is_current):
    colour = run_page.TONE_COLOURS[summary['tone']]
    names = summary['op_names']
    ops = '%s · %s' % (run_page.plural(len(names), 'op'), counts_words(summary['counts']) or 'none')
    if names:
        ops += ' · ' + ' '.join(names[:OP_NAMES_SHOWN]) + (' …' if len(names) > OP_NAMES_SHOWN else '')
    changed = ''
    if summary['changed']:
        shown = summary['changed'][:CHANGED_SHOWN]
        more = len(summary['changed']) - len(shown)
        changed = ('<div style="font-family:Menlo,monospace;font-size:12px;margin-top:4px;'
                   'color:var(--text)">%s%s</div>'
                   % ('<br>'.join(escape(path) for path in shown),
                      '<br>+%d more' % more if more > 0 else ''))
    style = ('padding:10px 12px;margin:8px 0;border-radius:10px;background:var(--wash);'
             'box-shadow:inset 3px 0 0 %s;%s'
             % (colour, 'outline:1.5px solid var(--accent);' if is_current else ''))
    verdict_word = VERDICT_WORDS[summary['tone']]
    pill = (visuals.badge(verdict_word.upper(), colour=colour)
            if visuals is not None and hasattr(visuals, 'badge') else '')
    return ('<div%s style="%s">'
            '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<b style="color:%s">%s</b>%s</span>'
            '<span style="color:var(--muted)">%s</span></div>'
            '<div style="color:var(--muted);font-size:13px;margin-top:3px">%s</div>%s</div>'
            % (page.go(run_page.history_item(summary['stamp'])), style, colour,
               escape(verdict_word), pill, escape(summary['when']),
               escape(ops), changed))


def build_runs(summaries, current=None):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    run_page.section_label(page, 'RECENT RUNS', '%d shown' % len(summaries))
    back = ('<div class="av-button"%s>◀ Back to run</div>' % page.go(BACK_TO_RUN)
            if current else '')
    page.parts.append('<div class="av-buttons">%s<div class="av-button"%s>↻ Refresh</div></div>'
                      % (back, page.go(REFRESH)))
    if not summaries:
        page.parts.append('<div style="color:var(--muted)">No stored runs yet.</div>')
    for summary in summaries:
        page.parts.append(run_card(page, summary, summary['stamp'] == current))
    page.parts.append('</div>')
    return page