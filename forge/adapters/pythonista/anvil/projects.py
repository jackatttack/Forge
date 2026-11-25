"""Projects for Anvil: the registered projects and notes left on them.

Role: gather · Part of: anvil/projects · Pure

    from anvil import projects
    rows = projects.load_projects(workspace)          # every registered project
    notes = projects.notes_for('anvil', workspace)    # newest first
    projects.add_note(project, 'Check Other on iPad', workspace)

Projects come from PROJECTS' catalogue (projects/project_hub/notes/
catalogue.json, schema 1, a "projects" list). Notes are MEMORY entries:
kind code, tagged with the project id and project-note, saved through the
journal's own add_entry exactly as MEMORY add does. So PROJECTS brief lists
them with the project's memories and MEMORY search finds them.

No ui. add_note is the only write.
"""
import json
import os
import sys


# --- Settings ---------------------------------------------------------------

DEFAULT_WORKSPACE = os.path.expanduser('~/Documents')
CATALOGUE = os.path.join('projects', 'project_hub', 'notes', 'catalogue.json')
MEMORY_INDEX = os.path.join('library', 'journal', 'index.json')
JOURNAL_LIBRARY = 'library'          # the folder that holds the journal package
NOTE_KIND = 'code'                   # the kind PROJECTS brief reads memories from
NOTE_TAG = 'project-note'
NOTE_PREFIX = 'Note on %s: '         # how a note starts in the journal (title)
NOTES_SHOWN = 12


# --- Projects ---------------------------------------------------------------

def load_json(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def is_active(project):
    return str(project.get('status') or '').startswith('active')


def load_projects(workspace=DEFAULT_WORKSPACE):
    """Registered projects, active ones first, then by id. [] if the
    catalogue cannot be read."""
    try:
        data = load_json(os.path.join(workspace, CATALOGUE))
    except (OSError, ValueError):
        return []
    rows = [item for item in data.get('projects') or []
            if isinstance(item, dict) and item.get('id')]
    return sorted(rows, key=lambda item: (not is_active(item), item['id']))


def find_project(projects, project_id):
    for project in projects:
        if project['id'] == project_id:
            return project
    return None


def available(workspace=DEFAULT_WORKSPACE):
    """True when PROJECTS' catalogue is here. The Projects page shows only
    then: a fresh Forge install has no catalogue and no journal."""
    return os.path.isfile(os.path.join(workspace, CATALOGUE))


# --- Notes ------------------------------------------------------------------

_index_cache = {}                    # index path -> (modified time, entries)


def memory_index(workspace):
    """The journal's index entries, re-read only when the file changes."""
    path = os.path.join(workspace, MEMORY_INDEX)
    try:
        modified = os.path.getmtime(path)
    except OSError:
        return []
    cached = _index_cache.get(path)
    if cached is not None and cached[0] == modified:
        return cached[1]
    try:
        entries = load_json(path)
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        entries = []
    _index_cache[path] = (modified, entries)
    return entries


def shown_text(preview):
    """A note's words without the 'Note on <title>: ' it is saved with."""
    text = str(preview or '')
    if text.startswith('Note on ') and ': ' in text:
        return text.split(': ', 1)[1]
    return text


def notes_for(project_id, workspace=DEFAULT_WORKSPACE, limit=NOTES_SHOWN):
    """[{'id', 'ts', 'text'}] for the project's notes, newest first. The text
    is the journal's preview, so a long note may be cut short here."""
    wanted = str(project_id).lower()
    found = []
    for entry in memory_index(workspace):
        if not isinstance(entry, dict) or not isinstance(entry.get('tags'), list):
            continue
        tags = [str(tag).lower() for tag in entry['tags']]
        if NOTE_TAG in tags and wanted in tags:
            found.append({'id': str(entry.get('id') or ''),
                          'ts': str(entry.get('ts') or entry.get('date') or ''),
                          'text': shown_text(entry.get('preview'))})
    found.sort(key=lambda note: (note['ts'], note['id']), reverse=True)
    return found[:limit]


def note_text(project, text):
    return NOTE_PREFIX % (project.get('title') or project['id']) + text.strip()


def add_note(project, text, workspace=DEFAULT_WORKSPACE):
    """Save text as a note on project (a catalogue row). Returns the journal
    entry. Raises if the journal is missing or the write fails."""
    library = os.path.join(workspace, JOURNAL_LIBRARY)
    if library not in sys.path:
        sys.path.insert(0, library)
    from journal.store import add_entry
    return add_entry(note_text(project, text), kind=NOTE_KIND,
                     tags=[project['id'], NOTE_TAG])