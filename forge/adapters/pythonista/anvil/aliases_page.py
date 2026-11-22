# -*- coding: utf-8 -*-
"""Anvil's Aliases page: Forge's aliases by tag, and one alias in full.

Pure: build_list and build_detail turn aliases_data's {name: entry} into
cards.Page objects, in Help's look (help_page.CSS). On an alias's page
each field is its own row, edited on its own. Taps
hand back:

    ('alias', name)                 show one alias
    ('alias_new',)                  + New alias (name, then expansion)
    ('alias_field', name, field)    edit one field: name, tag, description,
                                    hints or expansion
    ('alias_copy', name)            copy the one-liner
    ('alias_args', name)            ask for arguments, then copy the line
    ('alias_remove', name)          🗑 Remove; the second tap removes
    ('aliases_refresh',)            reread aliases.json
    ('alias_back',)                 ◀ Aliases: back to the list
"""
from editorkit.web import cards, prose

from . import aliases_data
from . import help_page
from . import page as run_page

escape = help_page.escape

DANGER = '#e5534b'
NEW = ('alias_new',)
REFRESH = ('aliases_refresh',)
BACK = ('alias_back',)
ROW_FIELDS = ('name', 'tag', 'description', 'hints')    # rows; the expansion has its own block
EMPTY_WORDS = 'none: tap to add'

CSS = """
.al-label{font-family:Menlo,monospace;font-size:11px;letter-spacing:.04em;color:var(--muted)}
.al-value{font-size:15px;line-height:1.4;color:var(--text);margin-top:2px}
.al-value.al-code{font-family:Menlo,monospace;font-weight:600;color:var(--accent)}
.al-value.al-empty{color:var(--muted);font-style:italic}
"""


# --- The list ---------------------------------------------------------------

def alias_row(page, name, entry):
    description = str(entry.get('description') or '')
    hints = aliases_data.hints_of(entry)
    return ('<div class="hp-row"%s><div class="hp-name">%s</div>%s%s</div>'
            % (page.go(('alias', name)), escape(aliases_data.usage(name, entry)),
               ('<div class="hp-words">%s</div>' % escape(description)) if description else '',
               ('<div class="hp-slug">%s</div>' % escape(' · '.join(hints))) if hints else ''))


def build_list(aliases):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    page.parts.append('<div class="av-buttons"><div class="av-button"%s>+ New alias</div>'
                      '<div class="av-button"%s>↻ Refresh</div></div>'
                      % (page.go(NEW), page.go(REFRESH)))
    if not aliases:
        page.parts.append('<div class="hp-none">No aliases yet. + New alias makes one; Forge '
                          'expands it when its name is a bundle on its own.</div>')
    for tag, members in aliases_data.groups(aliases):
        help_page.add_section(page, (tag or 'untagged').upper(), '%d' % len(members),
                              [alias_row(page, name, entry) for name, entry in members])
    page.parts.append('</div>')
    return page


# --- One alias --------------------------------------------------------------

def field_row(page, name, fields, field):
    text = aliases_data.field_text(fields, field)
    if field == 'hints' and text:
        text = ' · '.join(fields['hints'])
    classes = 'al-value' + (' al-code' if field == 'name' else '') + ('' if text else ' al-empty')
    return ('<div class="hp-row"%s><div class="al-label">%s</div><div class="%s">%s</div></div>'
            % (page.go(('alias_field', name, field)), escape(aliases_data.field_label(field).upper()),
               classes, escape(text or EMPTY_WORDS)))


def build_detail(name, entry, removing=False):
    """removing: 🗑 was tapped once, so it now asks for the second tap."""
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    fields = aliases_data.fields_of(name, entry)
    marks = aliases_data.placeholders(entry)
    run_button = (('Fill in arguments…', ('alias_args', name)) if marks
                  else ('Copy one-liner', ('alias_copy', name)))
    remove_html = ('<div class="av-button"%s style="color:%s;font-weight:600">Tap again to remove</div>'
                   % (page.go(('alias_remove', name)), DANGER) if removing
                   else '<div class="av-button"%s>🗑 Remove</div>' % page.go(('alias_remove', name)))
    page.parts.append('<div class="av-buttons"><div class="av-button"%s>◀ Aliases</div></div>'
                      % page.go(BACK))
    page.parts.append('<div class="av-buttons"><div class="av-button"%s>%s</div>%s</div>'
                      % (page.go(run_button[1]), escape(run_button[0]), remove_html))

    page.parts.append('<div class="hp-group">%s</div>'
                      % ''.join(field_row(page, name, fields, field) for field in ROW_FIELDS))

    blocks = [prose.heading('Run it', 3), prose.code(aliases_data.usage(name, entry), python=False)]
    if marks:
        blocks.append(prose.text('Arguments fill `$1`, `$2` … in the expansion; `$*` takes '
                                 'them all, `$-1` the last, `$^` all but the last.'))
    page.parts.append(prose.article(*blocks))

    run_page.section_label(page, 'EXPANSION', '%d lines' % len(fields['expansion'].splitlines()))
    page.parts.append('<div class="av-buttons"><div class="av-button"%s>✎ Edit expansion</div></div>'
                      % page.go(('alias_field', name, 'expansion')))
    page.parts.append(prose.article(prose.code(fields['expansion'], python=False)))
    page.parts.append('</div>')
    return page