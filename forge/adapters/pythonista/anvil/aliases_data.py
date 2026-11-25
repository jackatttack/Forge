"""Forge's aliases for Anvil's Aliases page: find aliases.json, read it,
check an edit and write it back.

Role: gather, store · Part of: anvil/aliases · Pure

Pure Python, no ui. Reading and writing go through Forge's own
forge.core.aliases (normalise_aliases, save_aliases), so the file keeps the
shape the ALIAS op writes. Anvil writes straight to the file (a design
choice, 2026-11-18); the copy it replaces is kept beside it as
aliases.json.anvil-backup, one step back. A file that will not read is
never written over.

An alias is edited one field at a time (separate fields, not one block).
Fields are a plain dict:

    {'name': 'boot', 'tag': 'forge' or None, 'description': '...',
     'hints': ['files', 'ops'], 'expansion': 'MAP .\\nDEPTH: 2'}

fields_of(name, entry) reads one; with_field(fields, field, typed) checks
and changes one field; apply_edit(aliases, old_name, fields) puts it back.
"""
import json
import os
import re
import shutil


# --- Settings ---------------------------------------------------------------

BACKUP_SUFFIX = '.anvil-backup'
RUNS_CHECKED = 3                   # newest stored runs asked where aliases.json is
NAME_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]*$')
PLACEHOLDER = re.compile(r'\$(\d+|\*|-1|\^)')

FIELDS = (                         # (field, label, what the composer says about it)
    ('name', 'Name', 'The word you send to Forge to run it. Start with a letter; '
                     'then letters, digits, _ . or -.'),
    ('tag', 'Tag', 'One word that groups it in the list. Empty: untagged.'),
    ('description', 'Description', 'What it does, in a line.'),
    ('hints', 'Hints', 'Labels, space-separated. They never change what it runs.'),
    ('expansion', 'Expansion', 'The bundle it runs. $1 $2 take arguments, $* all of '
                               'them, $-1 the last.'),
)


# --- Where the file is, reading and writing ---------------------------------

def aliases_path(runs_folder):
    """aliases.json as the newest stored runs' environment names it, else
    forge_home/aliases.json (forge_home holds artifacts/runs)."""
    try:
        stamps = sorted((name for name in os.listdir(runs_folder) if name[:1].isdigit()),
                        reverse=True)
    except Exception:
        stamps = []
    for stamp in stamps[:RUNS_CHECKED]:
        try:
            with open(os.path.join(runs_folder, stamp, 'run.json'), 'r', encoding='utf-8') as handle:
                path = (json.load(handle).get('environment') or {}).get('aliases_path')
            if path:
                return path
        except Exception:
            continue
    forge_home = os.path.dirname(os.path.dirname(runs_folder.rstrip(os.sep)))
    return os.path.join(forge_home, 'aliases.json')


def load(path):
    """{name: entry} in Forge's canonical shape; {} when there is no file.
    A file that will not read raises ValueError, so nothing saves over it."""
    from forge.core.aliases import normalise_aliases
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except Exception as error:
        raise ValueError('aliases.json did not read (%s): nothing was changed' % error)
    return normalise_aliases(data)


def save(path, aliases):
    """Write aliases through Forge, keeping the old file as the backup."""
    from forge.core.aliases import save_aliases
    if os.path.isfile(path):
        shutil.copyfile(path, path + BACKUP_SUFFIX)
    return save_aliases(aliases, environment={'aliases_path': path})


# --- Reading one alias ------------------------------------------------------

def hints_of(entry):
    hints = entry.get('hints')
    if isinstance(hints, str):
        return hints.split()
    if isinstance(hints, (list, tuple)):
        return [str(hint) for hint in hints]
    return []


def placeholders(entry):
    """The $ marks in the expansion, first seen first: '1', '2', '*', '-1', '^'."""
    found = []
    for mark in PLACEHOLDER.findall(str(entry.get('expansion') or '')):
        if mark not in found:
            found.append(mark)
    return found


def usage(name, entry):
    """How to run it: 'boot', 'readproj <1>', 'grep <1> <more…>'."""
    marks = placeholders(entry)
    numbered = sorted(int(mark) for mark in marks if mark.isdigit())
    words = ['<%d>' % number for number in range(1, (numbered[-1] if numbered else 0) + 1)]
    if any(mark in ('*', '^', '-1') for mark in marks):
        words.append('<more…>')
    return ' '.join([name] + words)


def groups(aliases):
    """[(tag, [(name, entry)])]: tags A to Z, untagged ('') last."""
    by_tag = {}
    for name in sorted(aliases, key=lambda name: name.lower()):
        tag = str(aliases[name].get('tag') or '').strip()
        by_tag.setdefault(tag, []).append((name, aliases[name]))
    tags = sorted((tag for tag in by_tag if tag), key=lambda tag: tag.lower())
    if '' in by_tag:
        tags.append('')
    return [(tag, by_tag[tag]) for tag in tags]


# --- Fields -----------------------------------------------------------------

def field_label(field):
    return dict((key, label) for key, label, hint in FIELDS).get(field, field)


def field_hint(field):
    return dict((key, hint) for key, label, hint in FIELDS).get(field, '')


def blank_fields():
    return {'name': '', 'tag': None, 'description': '', 'hints': [], 'expansion': ''}


def fields_of(name, entry):
    return {'name': name, 'tag': entry.get('tag') or None,
            'description': str(entry.get('description') or ''),
            'hints': hints_of(entry), 'expansion': str(entry.get('expansion') or '')}


def field_text(fields, field):
    """One field as the composer shows it."""
    value = fields.get(field)
    if field == 'hints':
        return ' '.join(value or [])
    return str(value or '')


def check_name(name, op_names=()):
    if not NAME_PATTERN.match(name):
        raise ValueError('"%s" is not an alias name: start with a letter, then '
                         'letters, digits, _ . or -.' % name)
    if name.upper() in set(str(op).upper() for op in op_names):
        raise ValueError('%s is a Forge operation, and real ops always win: pick another name.' % name)


def with_field(fields, field, typed, op_names=()):
    """fields with field set from the composer's text, checked. Raises
    ValueError saying what to fix. op_names: Forge's ops; an alias may not
    take one's name."""
    fields = dict(fields)
    text = str(typed)
    if field == 'name':
        name = text.strip()
        check_name(name, op_names)
        fields['name'] = name
    elif field == 'tag':
        fields['tag'] = text.strip() or None
    elif field == 'description':
        fields['description'] = ' '.join(text.split())
    elif field == 'hints':
        fields['hints'] = text.split()
    elif field == 'expansion':
        expansion = text.replace('\r\n', '\n').strip('\n').rstrip()
        if not expansion.strip():
            raise ValueError('An alias needs an expansion: the bundle it runs.')
        fields['expansion'] = expansion
    else:
        raise ValueError('No field called %s.' % field)
    return fields


# --- Writing one alias back -------------------------------------------------

def hint_value(hints, aliases):
    """Hints stored the way the file already stores them (text or list)."""
    for entry in aliases.values():
        if isinstance(entry.get('hints'), str):
            return ' '.join(hints)
        if isinstance(entry.get('hints'), list):
            return list(hints)
    return list(hints)


def apply_edit(aliases, old_name, fields):
    """A new {name: entry} with fields saved: a new alias (old_name None),
    an edit, or a rename (the name changed). Other keys on the entry are
    kept. Taking another alias's name raises ValueError."""
    aliases = dict(aliases)
    name = fields['name']
    if name != old_name and name in aliases:
        raise ValueError('There is already an alias called %s.' % name)
    entry = dict(aliases.get(old_name) or {}) if old_name else {'args': []}
    entry['expansion'] = fields['expansion']
    entry['tag'] = fields['tag']
    entry['description'] = fields['description']
    if fields['hints'] or 'hints' in entry:
        entry['hints'] = hint_value(fields['hints'], aliases)
    if old_name and old_name != name:
        aliases.pop(old_name, None)
    aliases[name] = entry
    return aliases