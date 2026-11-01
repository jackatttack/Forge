"""Forge Landing model: everything the landing shows, from a Forge run.

Pure Python with no ui, so it can be checked headlessly:

    python -m forge.adapters.pythonista.landing.model <run stamp>

Inputs are the run dict Forge hands to after_run (or a stored run.json),
plus optional live timings from Forge's console renderer: a list of
(op, target, elapsed_seconds) in run order. Stored runs carry no timings.
"""
import json
import os
import sys

RUNS_FOLDER = os.path.expanduser('~/.forge/artifacts/runs')
SPACED_WORD_GAP = '   '
TONE_GLYPH = {'success': '✓', 'warning': '–', 'danger': '✕'}
EDIT_OPS = ('WRITE', 'REPLACE', 'INSERT', 'DELETE')


def spaced(text):
    """'RUN CLEAN' -> 'R U N   C L E A N', the banner style of the live renderer."""
    return SPACED_WORD_GAP.join(' '.join(word) for word in str(text).split())


def status_tone(status):
    status = str(status or '').upper()
    if status.startswith('APPLIED'):
        return 'success'
    if status.startswith('SKIPPED'):
        return 'warning'
    return 'danger'


def format_bytes(count):
    count = int(count or 0)
    return '%d B' % count if count < 1024 else '%.1f KB' % (count / 1024.0)


def numbered(text, first_line=1):
    """Prefix each line with its line number, editor style."""
    return '\n'.join('%5d  %s' % (first_line + index, line)
                     for index, line in enumerate(str(text).splitlines()))


# --- Where an op touched a file ---------------------------------------------
def locate_new_text(path, parsed_op, project_root):
    """Lines a REPLACE landed on, found by searching for its new text.

    REPLACE results record no line numbers, but the parsed op keeps the new
    text. Exact unless the file has changed since the run.
    """
    if not parsed_op:
        return None
    directives = parsed_op.get('directives') or {}
    if directives.get('LINES'):
        try:
            first = int(str(directives['LINES']).split('-')[0])
            return first, first
        except ValueError:
            pass
    new_text = None
    for key, value in (parsed_op.get('blocks') or {}).items():
        if 'NEW' in str(key).upper():
            new_text = value
    if new_text is None:
        new_text = parsed_op.get('body')
    new_text = str(new_text or '').strip('\n')
    if not new_text:
        return None
    try:
        with open(os.path.join(project_root, path), encoding='utf-8') as source:
            text = source.read()
    except (OSError, UnicodeDecodeError):
        return None
    index = text.find(new_text)
    if index < 0:
        return None
    first = text.count('\n', 0, index) + 1
    return first, first + new_text.count('\n')


def find_location(result, parsed_op, project_root):
    """(path, first line, last line) of what an op touched, or Nones."""
    nothing = (None, None, None)
    data = result.get('data') if isinstance(result.get('data'), dict) else {}
    path = data.get('path') or result.get('file')
    if not isinstance(path, str) or not path:
        return nothing
    if ':' in path.split('/')[0]:
        return nothing  # named roots such as icloud: cannot open in the editor
    if not os.path.isfile(os.path.join(project_root, path)):
        return nothing
    if data.get('landed_start'):
        first = int(data['landed_start'])
        return path, first, int(data.get('landed_end') or first)
    if result.get('op') == 'READ' and data.get('start'):
        first = int(data['start'])
        return path, first, int(data.get('end') or first)
    if result.get('op') == 'REPLACE':
        lines = locate_new_text(path, parsed_op, project_root)
        if lines:
            return path, lines[0], lines[1]
    return path, 1, 1


# --- One row per op ---------------------------------------------------------
class OpRow(object):

    def __init__(self, number, total, result, parsed_op, seconds, project_root):
        self.number = number
        self.total = total
        self.op = str(result.get('op') or '?')
        self.status = str(result.get('status') or '')
        self.tone = status_tone(self.status)
        self.glyph = TONE_GLYPH[self.tone]
        self.target = str(result.get('target') or result.get('args') or '')
        self.message = str(result.get('message') or '')
        self.preview = str(result.get('preview') or '')
        self.seconds = seconds
        self.parsed_op = parsed_op or {}
        self.path, self.start_line, self.end_line = find_location(
            result, parsed_op, project_root)

    @property
    def counter(self):
        return '%02d/%02d' % (self.number, self.total)

    def short_target(self, width=40):
        text = self.target.replace('\n', ' ')
        return text if len(text) <= width else '…' + text[-(width - 1):]

    def change_text(self):
        """What this op wrote, as numbered lines, for the detail card.

        WRITE shows the whole body, INSERT the inserted lines numbered from
        where they landed, REPLACE its old lines (-) and new lines (+).
        Other ops fall back to their packet preview.
        """
        blocks = self.parsed_op.get('blocks') or {}
        body = str(self.parsed_op.get('body') or '')
        start = self.start_line or 1
        if self.op == 'REPLACE' and blocks:
            old_text, new_text = '', ''
            for key, value in blocks.items():
                if 'OLD' in str(key).upper():
                    old_text = str(value)
                if 'NEW' in str(key).upper():
                    new_text = str(value)
            lines = ['-       %s' % line for line in old_text.splitlines()]
            lines += ['+ %5d  %s' % (start + index, line)
                      for index, line in enumerate(new_text.splitlines())]
            return '\n'.join(lines)
        if body and self.op in ('WRITE', 'INSERT', 'REPLACE'):
            return numbered(body, start)
        return self.preview


class LandingModel(object):

    def __init__(self, run, timings=None, run_elapsed=None, project_root=None):
        self.stamp = str(run.get('stamp') or '')
        self.mode = str(run.get('mode') or 'dev')
        self.status = str(run.get('status') or '')
        self.packet = str(run.get('packet') or '')
        self.packet_bytes = run.get('packet_bytes') or len(self.packet.encode('utf-8'))
        self.project_root = (project_root or run.get('project_root')
                             or os.path.expanduser('~/Documents'))
        self.touched_files = list(run.get('touched_files') or [])

        results = [r for r in (run.get('results') or []) if isinstance(r, dict)]
        parsed_ops = run.get('parsed_ops') or []
        seconds = [float(entry[2]) for entry in (timings or [])]
        self.has_timings = bool(results) and len(seconds) == len(results)

        self.rows = []
        for index, result in enumerate(results):
            parsed_op = parsed_ops[index] if index < len(parsed_ops) else None
            self.rows.append(OpRow(index + 1, len(results), result, parsed_op,
                                   seconds[index] if self.has_timings else None,
                                   self.project_root))

        self.counts = {'success': 0, 'warning': 0, 'danger': 0}
        for row in self.rows:
            self.counts[row.tone] += 1
        if run_elapsed:
            self.total_seconds = float(run_elapsed)
        else:
            self.total_seconds = sum(seconds) if self.has_timings else None
        self.slowest = max([row.seconds for row in self.rows if row.seconds] + [0.001])

    @property
    def verdict(self):
        """(banner text, tone)."""
        # A run that fails to parse has no op rows, so read its own status too.
        if self.counts['danger'] or self.status.upper().startswith('FAILED'):
            return 'RUN FAILED', 'danger'
        if self.counts['warning']:
            return 'RUN PARTIAL', 'warning'
        return 'RUN CLEAN', 'success'

    def summary_line(self):
        parts = ['%d operations' % len(self.rows)]
        if self.total_seconds is not None:
            parts.append('%.2fs total' % self.total_seconds)
        parts.append('Packet %s' % format_bytes(self.packet_bytes))
        return '  ·  '.join(parts)

    def last_edit(self):
        """The last row that edited a file, else the last row with a file."""
        with_path = [row for row in self.rows if row.path]
        edits = [row for row in with_path if row.op in EDIT_OPS]
        if edits:
            return edits[-1]
        return with_path[-1] if with_path else None


# --- Stored runs ------------------------------------------------------------
def load_stored_run(stamp=None):
    """A run.json from Forge's run history; the latest finished run by default."""
    if stamp:
        folder = os.path.join(RUNS_FOLDER, stamp)
    else:
        names = sorted(name for name in os.listdir(RUNS_FOLDER)
                       if os.path.isfile(os.path.join(RUNS_FOLDER, name, 'run.json')))
        folder = os.path.join(RUNS_FOLDER, names[-1])
    with open(os.path.join(folder, 'run.json'), encoding='utf-8') as run_file:
        return json.load(run_file)


def main():
    model = LandingModel(load_stored_run(sys.argv[1] if len(sys.argv) > 1 else None))
    print('run %s  verdict %s  (%s)' % (model.stamp, model.verdict[0], spaced(model.verdict[0])))
    print(model.summary_line())
    for row in model.rows:
        where = '%s:%s-%s' % (row.path, row.start_line, row.end_line) if row.path else '-'
        print('%s %s %-8s %-8s %s' % (row.glyph, row.counter, row.op, row.status[:8], where))
    edit = model.last_edit()
    print('last edit:', edit.op if edit else None, edit.path if edit else '')


if __name__ == '__main__':
    main()