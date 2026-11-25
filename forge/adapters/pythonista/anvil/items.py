"""What a bundle asks for: EDITOR items, the answers given, and the reply.

Role: contracts, clean · Part of: anvil/items · Pure

Pure (no ui): tests/smoke_items.py checks it.

    items = collect(run)                    # from the EDITOR op's result data
    answers = load_answers(stamp)           # {'1': {'value': 'no'}, ...}
    save_answers(stamp, answers)            # anvil.json in the run's folder
    text = reply_text(stamp, items, answers)

An item is a dict: kind ('open', 'ask', 'check', 'note'), number (1-based,
in bundle order), skipped, and text / options / path / target_line by kind.
Answers are keyed by the item's number as a string, because they are
stored as JSON. An ASK's value is the chosen or typed answer; a CHECK's is
True once ticked.
"""
import json
import os


# --- Settings ---------------------------------------------------------------

RUNS_FOLDER = os.path.expanduser('~/.forge/artifacts/runs')
ANSWERS_FILE = 'anvil.json'
ANSWERABLE = ('ask', 'check')        # kinds that go into the reply as answers
NEEDS_CLEAN_RUN = ('open', 'check', 'ask')  # kinds held when the run was not clean:
                                            # a device question about work that did not land is moot


# --- Items ------------------------------------------------------------------

def run_is_clean(run):
    """True when the run and every operation in it applied."""
    def applied(status):
        return str(status or '').upper().startswith('APPLIED')

    if not applied((run or {}).get('status')):
        return False
    return all(applied(result.get('status'))
               for result in (run or {}).get('results') or []
               if isinstance(result, dict))


def collect(run):
    """Every item the run's EDITOR ops handed over, numbered in bundle order."""
    clean = run_is_clean(run)
    found = []
    for result in (run or {}).get('results') or []:
        data = result.get('data') if isinstance(result, dict) else None
        handed = data.get('anvil') if isinstance(data, dict) else None
        for item in (handed or {}).get('items') or []:
            item = dict(item)
            item['number'] = len(found) + 1
            item['skipped'] = bool(item.get('missing')) or (
                item.get('kind') in NEEDS_CLEAN_RUN and not clean)
            found.append(item)
    return found


def answerable(items):
    """The items still open to answer: ASK and CHECK that were not skipped."""
    return [item for item in items
            if item.get('kind') in ANSWERABLE and not item.get('skipped')]


def is_answered(item, answers):
    value = ((answers or {}).get(str(item['number'])) or {}).get('value')
    if item.get('kind') == 'check':
        return value is True
    return bool(value)


def answered_count(items, answers):
    return sum(1 for item in answerable(items) if is_answered(item, answers))


# --- Answers on disk --------------------------------------------------------

def answers_path(stamp, runs_folder=RUNS_FOLDER):
    return os.path.join(runs_folder, str(stamp), ANSWERS_FILE)


def load_answers(stamp, runs_folder=RUNS_FOLDER):
    """The saved answers for a run, or {} when there are none."""
    try:
        with open(answers_path(stamp, runs_folder), 'r', encoding='utf-8') as handle:
            stored = json.load(handle)
        return dict(stored.get('answers') or {})
    except (OSError, ValueError, AttributeError):
        return {}


def save_answers(stamp, answers, runs_folder=RUNS_FOLDER):
    """Save answers beside the run. False when the run's folder is gone
    (Forge keeps a limited number of runs)."""
    path = answers_path(stamp, runs_folder)
    if not stamp or not os.path.isdir(os.path.dirname(path)):
        return False
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump({'answers': answers}, handle, indent=2)
    os.replace(temporary, path)
    return True


# --- The way back to the chat -----------------------------------------------

NOTES_KEY = 'notes'          # the reader's notes on a run, saved beside its answers


def notes_of(answers):
    """The notes written on a run, or ''."""
    return str(((answers or {}).get(NOTES_KEY) or {}).get('value') or '')


def with_notes(answers, text):
    """answers with the notes set to text; blank text removes them."""
    answers = dict(answers or {})
    text = str(text or '').rstrip()
    if text.strip():
        answers[NOTES_KEY] = {'value': text}
    else:
        answers.pop(NOTES_KEY, None)
    return answers


def reply_text(stamp, items, answers):
    """The REPLY block appended to the packet by Copy packet with reply:
    each item's answer, then the notes."""
    lines = ['=== REPLY ===', 'Run: %s' % stamp]
    for item in items:
        kind, number = item.get('kind'), item['number']
        value = ((answers or {}).get(str(number)) or {}).get('value')
        if kind == 'ask':
            if item.get('skipped'):
                outcome = 'held (the run was not clean)'
            else:
                outcome = value if value else 'not answered'
            lines.append('%d. ASK %s -> %s' % (number, item['text'], outcome))
        elif kind == 'check':
            if item.get('skipped'):
                outcome = 'skipped (the run was not clean)'
            else:
                outcome = 'done' if value is True else 'not done'
            lines.append('%d. CHECK %s -> %s' % (number, item['text'], outcome))
        elif kind == 'open' and item.get('skipped'):
            reason = 'file not found' if item.get('missing') else 'the run was not clean'
            lines.append('%d. OPEN %s -> not opened (%s)' % (number, item['path'], reason))
    notes = notes_of(answers)
    if notes:
        lines += ['NOTES', notes]
    return '\n'.join(lines)