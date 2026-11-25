"""Anvil's Projects page: every registered project, or one with its notes.

Role: present · Part of: anvil/projects · Pure

Pure: builds editorkit cards.Pages and touches no ui.

    page = build_list(projects)              # every project as a card
    page = build_detail(project, notes)      # status, next, notes, + Note

Taps hand back the items below; landing.py acts on them. The look is the
run page's own (page.py CSS), so the tile needs page.tile_css().
"""
from editorkit.web import cards

from . import page as run_page
from . import projects as project_data

escape = cards.escape


# --- Settings ---------------------------------------------------------------

CARD_WIDTH = 160                     # narrowest a project card gets
ACTIVE_COLOUR = run_page.FORGE_BLUE  # edge of an active project's card
NOTE_DATE_CHARACTERS = 16            # '2026-11-15T22:40' of an ISO timestamp


# --- Items taps hand back ---------------------------------------------------

BACK = ('projects_back',)


def project_item(project_id):
    """Show one project."""
    return ('project', project_id)


def note_item(project_id):
    """Type a note for a project."""
    return ('add_note', project_id)


# --- Pieces -----------------------------------------------------------------

def button_row(page, buttons):
    page.parts.append('<div class="av-buttons">%s</div>' % ''.join(
        '<div class="av-button"%s>%s</div>' % (page.go(item), escape(label))
        for label, item in buttons))


def project_card(project):
    return cards.Card(project.get('title') or project['id'],
                      item=project_item(project['id']),
                      body=cards.text(project.get('status') or 'no status'),
                      colour=ACTIVE_COLOUR if project_data.is_active(project) else None)


def field_html(label, words):
    if not words:
        return ''
    return ('<div class="av-field"><div class="av-field-label">%s</div>'
            '<div class="av-wait-text">%s</div></div>' % (escape(label), escape(words)))


def note_html(note):
    when = note['ts'][:NOTE_DATE_CHARACTERS].replace('T', ' ')
    return ('<div class="av-wait"><div class="av-note-date">%s</div>'
            '<div class="av-wait-text">%s</div></div>' % (escape(when), escape(note['text'])))


# --- The pages --------------------------------------------------------------

def build_list(projects):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    active = sum(1 for project in projects if project_data.is_active(project))
    run_page.section_label(page, 'PROJECTS', '%d active of %d' % (active, len(projects)))
    if projects:
        page.grid([project_card(project) for project in projects], min_width=CARD_WIDTH)
    else:
        page.parts.append('<div class="av-wait av-muted">'
                          'No projects found in the PROJECTS catalogue.</div>')
    page.parts.append('</div>')
    return page


def build_detail(project, notes):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    button_row(page, (('‹ Projects', BACK), ('+ Note', note_item(project['id']))))
    page.parts.append('<div class="av-project-title">%s</div>'
                      % escape(project.get('title') or project['id']))
    page.parts.append(field_html('STATUS', project.get('status'))
                      + field_html('NEXT', project.get('next'))
                      + field_html('PURPOSE', project.get('purpose'))
                      + field_html('PATH', project.get('path')))
    run_page.section_label(page, 'NOTES', run_page.plural(len(notes), 'note'))
    if notes:
        page.parts.append(''.join(note_html(note) for note in notes))
    else:
        page.parts.append('<div class="av-wait av-muted">No notes yet: + Note adds one.</div>')
    page.parts.append('</div>')
    return page
