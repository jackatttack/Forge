# -*- coding: utf-8 -*-
"""Op renders: an operation's output drawn from its result data, the way
the Toolbox draws code, instead of the packet's plain text.

Pure (no ui), so tests/smoke_renders.py checks it headless. Forge's OpRow
keeps only the packet preview, so the presenter attaches each result's data
to its row first:

    renders.attach_data(model, run)                          # forge_presenter
    context = renders.RenderContext(open_item, fold_item, unfolded)
    html = renders.detail_html(page, row, context)           # page.operation_html

detail_html returns None when no renderer fits or a renderer fails, and the
page shows the plain preview as before: a render can never cost anyone
the output.

Renderers (RENDERERS at the bottom) take (page, row, data, context) and
return HTML, or None for the plain preview:

    SEARCH    hits grouped by file, with context read fresh around each, in
              the code view's rows; a tap opens the file at that line
    READ      the lines read, with their real numbers; a tap opens there
    MAP       a directory tree: tap a folder to fold it, a file to open it.
              Other maps: each section's lines under its name
    RUN       exit code, then stdout and stderr; traceback frames inside the
              project open at their line, exception lines are tinted red
    MEMORY    a guide as prose; other MEMORY output as Forge text
    FORGE     help, config, ops and the rest as Forge text
    PROJECTS  lists and briefs as Forge text

Forge text: the plain text Forge's own commands print, read as prose.
Underlined and capitalised lines become headings, '- ' lines bullets,
'Key: value' runs a definition list; commands, tables and indented lines
stay as code.
"""
import os
import re

from editorkit.web import cards, codeview, prose

escape = cards.escape


# --- Settings ---------------------------------------------------------------

SEARCH_CONTEXT_LINES = 1     # lines read fresh above and below each hit (0: hits only)
SEARCH_HITS_SHOWN = 40       # hits drawn before "… more"
READ_LINES_SHOWN = 60        # lines of a READ drawn before "… more"
MAP_LINES_SHOWN = 80         # rows of a MAP tree drawn before "… more"
RUN_HEAD_LINES = 20          # first lines of a long stdout or stderr kept
RUN_TAIL_LINES = 60          # last lines kept (a test summary is at the end)
GUIDE_LINES_SHOWN = 160      # lines of a MEMORY guide drawn before "… more"
FORGE_TEXT_LINES_SHOWN = 200 # lines of Forge text drawn before "… more"
TERM_MAX_CHARACTERS = 24     # longest Key in a 'Key: value' line read as a term
FOLDER_MARK, PYTHON_MARK, FILE_MARK = '📁', '🐍', '📄'
FOLDED, UNFOLDED = '▸', '▾'

TRACE_FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+)')
EXCEPTION_LINE = re.compile(r'^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt|Warning)\b')
TEST_FAILURE_LINE = re.compile(r'^(FAIL|ERROR): ')
HEADING_RULE = re.compile(r'^[=\-]{3,}$')
TERM_LINE = re.compile(r'^([A-Za-z][\w .()/-]{0,%d}):\s+(\S.*)$' % (TERM_MAX_CHARACTERS - 1))


# --- Attaching the data and choosing a renderer -----------------------------

def attach_data(model, run):
    """Give each of model's rows its result (row.result), the result's data
    (row.data) and the project root (row.root). Rows line up with run's
    dict results, the way LandingModel builds them."""
    results = [result for result in (run.get('results') or []) if isinstance(result, dict)]
    for row, result in zip(model.rows, results):
        data = result.get('data')
        row.result = result
        row.data = data if isinstance(data, dict) else {}
        row.root = model.project_root


class RenderContext(object):
    """What renderers need from the page. open_item(path, line) and
    fold_item(name) make tap items; unfolded holds the fold names the user
    has flipped from their default."""

    def __init__(self, open_item, fold_item, unfolded=()):
        self.open_item = open_item
        self.fold_item = fold_item
        self.unfolded = set(unfolded)

    def is_open(self, name, default=True):
        return (name in self.unfolded) != default


def detail_html(page, row, context):
    """row's output rendered for its op, or None for the plain preview."""
    data = getattr(row, 'data', None)
    renderer = RENDERERS.get(row.op)
    if not data or renderer is None:
        return None
    try:
        return renderer(page, row, data, context)
    except Exception:            # a render must never cost the output
        return None


# --- Shared pieces ----------------------------------------------------------

def plural(count, word):
    return '%d %s%s' % (count, word, '' if count == 1 else 's')


def is_python(path):
    return str(path).split('::')[0].endswith('.py')


def meta_html(words):
    """A small muted line, the docs' look."""
    return prose.article(prose.meta(words))


def file_lines(root, path):
    """path's lines read fresh, or [] (another root, gone, unreadable)."""
    if not root or not path or ':' in str(path).split('/')[0]:
        return []
    try:
        with open(os.path.join(root, path), encoding='utf-8') as handle:
            return handle.read().splitlines()
    except Exception:
        return []


def project_relative(root, path):
    """path as a project-relative path when it is inside root, else None.
    /private/var and /var name the same place on iOS."""
    def bare(value):
        value = str(value)
        return value[len('/private'):] if value.startswith('/private/') else value
    if not root:
        return None
    base, full = bare(root).rstrip('/'), bare(path)
    if full.startswith(base + '/'):
        return full[len(base) + 1:]
    return None


def line_blocks(numbers, context, total):
    """[[first, last]]: each number with context lines either side, kept
    within 1..total, touching runs merged. total 0: the numbers alone."""
    blocks = []
    for number in sorted(set(numbers)):
        if total:
            first, last = max(1, number - context), min(total, number + context)
        else:
            first = last = number
        if blocks and first <= blocks[-1][1] + 1:
            blocks[-1][1] = max(blocks[-1][1], last)
        else:
            blocks.append([first, last])
    return blocks


def code_rows_html(page, label, label_item, blocks, python):
    """One file in the code view's own markup (its CSS is on every Cards
    page): a path line, then blocks of rows. A row is (css, number, text,
    item): css is 'row', 'row hit', 'row ctx', 'row error' or 'row note';
    item, or None, is what a tap hands back. Built here rather than with
    codeview.rows_section so taps go through page.go, like every other tap
    on Anvil's page."""
    out = ['<div class="file"><div class="path"%s>%s</div>'
           % (page.go(label_item) if label_item is not None else '', escape(label))]
    for block in blocks:
        out.append('<div class="block">')
        for css, number, text, item in block:
            if python and css != 'row note':
                code = codeview.line_html(text, codeview.syntax_classes(text).get(1, []), [])
            else:
                code = escape(text)
            out.append('<div class="%s"%s><span class="ln">%s</span><span class="code">%s</span></div>'
                       % (css, page.go(item) if item is not None else '',
                          '' if number is None else number, code))
        out.append('</div>')
    out.append('</div>')
    return ''.join(out)


# --- SEARCH -----------------------------------------------------------------

def search_html(page, row, data, context):
    hits = [hit for hit in (data.get('hits') or [])
            if isinstance(hit, dict) and hit.get('file') and isinstance(hit.get('line'), int)]
    if not hits:
        return None
    shown = hits[:SEARCH_HITS_SHOWN]
    order, text_by_file = [], {}
    for hit in shown:
        path = str(hit['file'])
        if path not in text_by_file:
            text_by_file[path] = {}
            order.append(path)
        text_by_file[path][hit['line']] = str(hit.get('text') or '')

    words = '%s for "%s" in %s' % (plural(len(hits), 'hit'), data.get('query', ''),
                                   plural(data.get('files_hit') or len(order), 'file'))
    if data.get('limit_reached'):
        words += ' · limit reached'
    parts = [meta_html(words)]
    for path in order:
        hit_text = text_by_file[path]
        lines = file_lines(getattr(row, 'root', ''), path)
        if lines and max(hit_text) > len(lines):
            lines = []               # the file changed since the run: hits alone
        around = SEARCH_CONTEXT_LINES if lines else 0
        blocks = []
        for first, last in line_blocks(hit_text, around, len(lines)):
            blocks.append([('row hit' if number in hit_text else 'row ctx', number,
                            lines[number - 1] if lines else hit_text[number],
                            context.open_item(path, number))
                           for number in range(first, last + 1)])
        label = '%s  ·  %s' % (path, plural(len(hit_text), 'hit'))
        parts.append(code_rows_html(page, label, context.open_item(path, min(hit_text)),
                                    blocks, is_python(path)))
    if len(hits) > len(shown):
        parts.append(meta_html('… %s more: the packet has them all.'
                               % plural(len(hits) - len(shown), 'hit')))
    return ''.join(parts)


# --- READ -------------------------------------------------------------------

def read_html(page, row, data, context):
    lines = data.get('lines')
    path = str(data.get('path') or row.path or '').split('::')[0]
    if not isinstance(lines, list) or not lines or not path:
        return None
    start = data.get('start') if isinstance(data.get('start'), int) else 1
    shown = lines[:READ_LINES_SHOWN]
    block = [('row', start + index, str(line), context.open_item(path, start + index))
             for index, line in enumerate(shown)]
    if len(lines) > len(shown):
        more_at = start + len(shown)
        block.append(('row note', None, '… %s: tap to open at line %d'
                      % (plural(len(lines) - len(shown), 'more line'), more_at),
                      context.open_item(path, more_at)))
    total = data.get('total')
    label = '%s  ·  lines %d-%d%s' % (path, start, start + len(lines) - 1,
                                      ' of %d' % total if isinstance(total, int) else '')
    return code_rows_html(page, label, context.open_item(path, start), [block], is_python(path))


# --- MAP --------------------------------------------------------------------

def tree_entries(lines):
    """[(depth, name, text)] from Structure lines: two spaces a level, name
    is the line up to any two-space gap, text the line without its indent."""
    entries = []
    for line in lines:
        line = str(line)
        text = line.strip()
        if text:
            depth = (len(line) - len(line.lstrip(' '))) // 2
            entries.append((depth, text.split('  ')[0], text))
    return entries


def folded_count(entries, index):
    """How many entries sit inside the folder at index."""
    depth, count = entries[index][0], 0
    for later_depth, name, text in entries[index + 1:]:
        if later_depth <= depth:
            break
        count += 1
    return count


def tree_rows(lines, context, row_number):
    """Structure lines as rows. Folders show a fold mark and fold on a tap
    (fold name ('tree', op number, folder path), open by default); files
    show a mark and open on a tap. Paths are rebuilt from the indentation;
    the first line is the mapped folder."""
    entries = tree_entries(lines)
    rows, folders, hidden_below = [], [], None
    for index, (depth, name, text) in enumerate(entries):
        if hidden_below is not None and depth > hidden_below:
            continue                 # inside a folded folder
        hidden_below = None
        if len(rows) >= MAP_LINES_SHOWN:
            rows.append(('row note', None, '… more entries: fold folders to see the rest', None))
            break
        del folders[depth:]
        indent = '  ' * depth
        if name.endswith('/'):
            folder = '/'.join(folders + [name.rstrip('/')])
            fold_name = ('tree', row_number, folder)
            is_open = context.is_open(fold_name)
            folders.append(name.rstrip('/'))
            label = '%s%s %s %s' % (indent, UNFOLDED if is_open else FOLDED, FOLDER_MARK, text)
            if not is_open:
                label += '  · %d' % folded_count(entries, index)
                hidden_below = depth
            rows.append(('row', None, label, context.fold_item(fold_name)))
        else:
            mark = PYTHON_MARK if name.endswith('.py') else FILE_MARK
            path = '/'.join(folders + [name])
            rows.append(('row', None, '%s  %s %s' % (indent, mark, text),
                         context.open_item(path, 1)))
    return rows


def map_html(page, row, data, context):
    sections = data.get('sections')
    if not isinstance(sections, dict) or not sections:
        return None
    fields = data.get('fields') if isinstance(data.get('fields'), dict) else {}
    facts = ['%s %s' % (fields[key], key) for key in ('files', 'dirs', 'python files')
             if key in fields]
    parts = [meta_html(' · '.join(facts))] if facts else []
    structure = sections.get('Structure')
    if data.get('map_type') == 'directory' and isinstance(structure, list):
        label = str(data.get('map_target') or row.target)
        parts.append(code_rows_html(page, label, None,
                                    [tree_rows(structure, context, row.number)], False))
        return ''.join(parts)
    for name, lines in sections.items():
        if isinstance(lines, list) and lines:
            block = [('row', None, str(line), None) for line in lines[:MAP_LINES_SHOWN]]
            if len(lines) > MAP_LINES_SHOWN:
                block.append(('row note', None, '… %s' % plural(len(lines) - MAP_LINES_SHOWN,
                                                                'more line'), None))
            parts.append(code_rows_html(page, str(name), None, [block], False))
    return ''.join(parts) or None


# --- RUN --------------------------------------------------------------------

def stream_rows(text, context, root):
    """One stream's lines as rows: long streams keep their head and tail,
    traceback frames inside the project become short paths that open at
    their line, exception and test-failure lines are tinted red."""
    lines = text.rstrip('\n').splitlines()
    hidden = len(lines) - RUN_HEAD_LINES - RUN_TAIL_LINES
    if hidden > 0:
        lines = lines[:RUN_HEAD_LINES] + [None] + lines[-RUN_TAIL_LINES:]
    rows = []
    for line in lines:
        if line is None:
            rows.append(('row note', None, '… %s' % plural(hidden, 'more line'), None))
            continue
        frame = TRACE_FRAME.match(line)
        place = project_relative(root, frame.group(1)) if frame else None
        if place:
            rows.append(('row hit', None, line.replace(frame.group(1), place),
                         context.open_item(place, int(frame.group(2)))))
        elif EXCEPTION_LINE.match(line) or TEST_FAILURE_LINE.match(line):
            rows.append(('row error', None, line, None))
        else:
            rows.append(('row', None, line, None))
    return rows


def run_html(page, row, data, context):
    if 'stdout' not in data and 'stderr' not in data:
        return None
    words = 'exit %s' % data.get('exit_code', '?')
    gate = (getattr(row, 'result', None) or {}).get('gate')
    if gate:
        words += ' · %s gate' % gate
    parts = [meta_html(words)]
    for name in ('stdout', 'stderr'):
        text = str(data.get(name) or '')
        if text.strip():
            rows = stream_rows(text, context, getattr(row, 'root', ''))
            parts.append(code_rows_html(page, name, None, [rows], False))
    if len(parts) == 1:
        parts.append(meta_html('No output.'))
    return ''.join(parts)


# --- Prose: guides and Forge text --------------------------------------------

class ProseBuilder(object):
    """Lines into prose blocks. Runs of one kind make one block: 'prose' (a
    paragraph), 'code' (a code block), 'terms' (a definition list). Each
    bullet is its own block, continued by its indented lines, and is joined
    onto one line so prose draws it as a list item."""

    def __init__(self):
        self.blocks, self.kind, self.held = [], None, []

    def add(self, kind, item):
        if kind != self.kind:
            self.finish()
            self.kind = kind
        self.held.append(item)

    def bullet(self, words):
        self.finish()
        self.kind = 'bullet'
        self.held.append(words)

    def heading(self, words, level):
        self.finish()
        self.blocks.append(prose.heading(words, level))

    def note(self, words):
        self.finish()
        self.blocks.append(prose.meta(words))

    def finish(self):
        kind, held = self.kind, self.held
        self.kind, self.held = None, []
        if not held:
            return
        if kind == 'code':
            self.blocks.append(prose.code('\n'.join(held), python=False))
        elif kind == 'terms':
            self.blocks.append(prose.terms(held))
        else:
            self.blocks.append(prose.text(' '.join(held)))

    def finished_blocks(self):
        self.finish()
        return list(self.blocks)

    def html(self):
        self.finish()
        return prose.article(*self.blocks) if self.blocks else None


def is_numbered(text):
    first = text.split(' ')[0]
    return len(first) > 1 and first.endswith('.') and first[:-1].isdigit()


def guide_lines(preview):
    """A guide's lines without Forge's footer (---, file:, Edit in place)."""
    lines = preview.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip() == '---':
            if any(line.startswith('file:') for line in lines[index + 1:]):
                return lines[:index]
            break
    return lines


def guide_html(text, slug):
    """A markdown guide: # headings, - and 1. bullets, Key: value terms."""
    lines = guide_lines(text)
    built = ProseBuilder()
    for line in lines[:GUIDE_LINES_SHOWN]:
        stripped = line.strip()
        level = len(stripped) - len(stripped.lstrip('#'))
        term = TERM_LINE.match(stripped)
        if 1 <= level <= 4 and stripped[level:level + 1] == ' ':
            built.heading(stripped[level:].strip(), level)
        elif not stripped:
            built.finish()
        elif stripped.startswith('- '):
            built.bullet('• ' + stripped[2:])
        elif is_numbered(stripped):
            built.bullet(stripped)
        elif built.kind == 'bullet' and line[:1] == ' ':
            built.held.append(stripped)
        elif term and line[:1] != ' ':
            built.add('terms', term.groups())
        else:
            built.add('prose', stripped)
    if len(lines) > GUIDE_LINES_SHOWN:
        built.note('… %s: MEMORY guide %s shows it all.'
                   % (plural(len(lines) - GUIDE_LINES_SHOWN, 'more line'), slug))
    return built.html()


def is_caps_heading(text):
    return (text == text.upper() and any(character.isalpha() for character in text)
            and len(text) <= 48 and not text.endswith('.') and ' | ' not in text)


def is_underline(rule, line):
    if len(rule) < 3 or not line or not HEADING_RULE.match(rule):
        return False
    return set(rule) == {'='} or len(rule) >= len(line) - 1


def is_code_line(line):
    """Commands (an upper-case op word), tables, aligned columns and
    indented lines: kept as code."""
    text = line.strip()
    first = text.split(' ')[0]
    return (line[:1] in (' ', '\t') or text[:1] in ('{', '}', '[', ']', '<', '$', '>')
            or ' | ' in text or '   ' in text
            or (len(first) > 1 and first.isalpha() and first.isupper()
                and not text.endswith('.')))


def forge_text_blocks(text, limit=FORGE_TEXT_LINES_SHOWN):
    """Forge's own plain text (help, config, briefs, lists) as prose blocks.

    Code: everything from a BEGIN_ marker to its END_ marker, and once a
    code block starts it runs on to the next blank line, so a bundle
    example stays one block to copy. A CAPS line is a heading only after a
    blank line; straight under other text it is a command."""
    lines = [line.rstrip() for line in str(text).splitlines()]
    limit = len(lines) if limit is None else limit     # None: every line (Help pages)
    built = ProseBuilder()
    index, shown = 0, min(len(lines), limit)
    in_body = False
    while index < shown:
        line = lines[index]
        stripped = line.strip()
        following = lines[index + 1].strip() if index + 1 < len(lines) else ''
        after_blank = index == 0 or not lines[index - 1].strip()
        term = TERM_LINE.match(stripped)
        if in_body:
            built.add('code', line)
            in_body = not stripped.startswith('END_')
        elif stripped.startswith('BEGIN_'):
            built.add('code', line)
            in_body = True
        elif not stripped:
            built.finish()
        elif is_underline(following, stripped):
            built.heading(stripped, 2)
            index += 1               # the underline itself
        elif HEADING_RULE.match(stripped):
            built.finish()
        elif built.kind == 'code':
            built.add('code', line)
        elif is_caps_heading(stripped) and after_blank:
            built.heading(stripped, 3)
        elif stripped.startswith('- ') and line[:1] != ' ':
            built.bullet('• ' + stripped[2:])
        elif built.kind == 'bullet' and line[:2] == '  ' and line[2:3] != ' ':
            built.held.append(stripped)
        elif stripped.endswith(':') and following.startswith('- '):
            built.heading(stripped[:-1], 4)      # 'Fix:' over its list
        elif is_code_line(line) or is_caps_heading(stripped):
            built.add('code', line)
        elif term:
            built.add('terms', term.groups())
        else:
            built.add('prose', stripped)
        index += 1
    if len(lines) > limit:
        built.note('… %s: the packet has it all.'
                   % plural(len(lines) - limit, 'more line'))
    return built.finished_blocks()


def forge_text_html(text):
    """Forge text as one prose article, or None when there is nothing."""
    blocks = forge_text_blocks(text)
    return prose.article(*blocks) if blocks else None


def memory_html(page, row, data, context):
    text = row.preview or row.message
    if not text.strip():
        return None
    if data.get('mode') == 'guide':
        return guide_html(text, data.get('slug', ''))
    return forge_text_html(text)


def forge_html(page, row, data, context):
    """FORGE and PROJECTS: PROJECTS prints its text as the message."""
    text = row.preview or row.message
    return forge_text_html(text) if text.strip() else None


RENDERERS = {
    'SEARCH': search_html,
    'READ': read_html,
    'MAP': map_html,
    'RUN': run_html,
    'MEMORY': memory_html,
    'FORGE': forge_html,
    'PROJECTS': forge_html,
}