# -*- coding: utf-8 -*-
"""Anvil's Help page: Forge's operations, its docs and the workspace's
guides, in the prose look of the Toolbox's Explain.

Pure: build_list, build_op and build_doc turn help_data's records into
cards.Page objects. Taps hand back:

    ('help_op', name)            an operation's full help
    ('help_doc', kind, name)     a Forge doc or a guide
    ('help_back',)               ◀ Help at the top: back to the list
    ('copy_text', text, done)    copy text, then say done

The list reads like a settings screen: one column of rows in rounded
groups, names in code type, words in the system font. A page ends with
its copy button and ↑ Top; going back is the ◀ in the window's header
(landing.py), so nothing sits over the words.

markdown_blocks reads READMEs and guides; Forge's plain text (its .txt
docs, the bundle grammar) goes through renders.forge_text_blocks.
"""
from editorkit.web import cards, prose

from . import page as run_page
from . import renders


# --- Settings ---------------------------------------------------------------

CODE_INDENT = '    '           # markdown: indented this far after a blank line is code
MARKDOWN_SNIFF_LINES = 40      # a # heading in this many lines: read as markdown
BACK = ('help_back',)

SANS = "-apple-system,system-ui,'Helvetica Neue',sans-serif"

CSS = """
.hp-group{background:var(--wash);border-radius:12px;overflow:hidden;margin:6px 0 16px}
.hp-row{position:relative;padding:10px 30px 10px 12px;cursor:pointer;font-family:SANS;
  border-top:1px solid var(--rule)}
.hp-row:first-child{border-top:none}
.hp-row::after{content:'\\203A';position:absolute;right:12px;top:50%;
  transform:translateY(-50%);color:var(--muted);font-size:20px}
.hp-name{font-family:Menlo,monospace;font-weight:600;font-size:14px;color:var(--accent)}
.hp-name.hp-local{color:var(--text)}
.hp-title{font-weight:600;font-size:15px;line-height:1.3;color:var(--text)}
.hp-words{font-size:14px;line-height:1.4;color:var(--muted);margin-top:2px}
.hp-slug{font-family:Menlo,monospace;font-size:11px;color:var(--muted);margin-top:4px}
.hp-none{color:var(--muted);margin:14px 4px;font-family:SANS}
.hp-foot{margin:20px 0 10px}
""".replace('SANS', SANS)


def escape(text):
    return cards.escape(str(text))


# --- The list ---------------------------------------------------------------

def op_row(page, op):
    return ('<div class="hp-row"%s><div class="hp-name%s">%s</div>'
            '<div class="hp-words">%s</div></div>'
            % (page.go(('help_op', op.name)), '' if op.public else ' hp-local',
               escape(op.name), escape(op.summary or 'No summary.')))


def doc_source(doc):
    if doc.kind == 'guide':
        return 'library/guides/%s.md' % doc.name
    return 'FORGE bundle' if doc.name == 'bundle' else 'FORGE docs %s' % doc.name


def doc_row(page, doc):
    return ('<div class="hp-row"%s><div class="hp-title">%s</div>'
            '<div class="hp-words">%s</div><div class="hp-slug">%s</div></div>'
            % (page.go(('help_doc', doc.kind, doc.name)), escape(doc.title),
               escape(doc.words), escape(doc_source(doc))))


def add_section(page, label, aside, rows):
    if not rows:
        return
    run_page.section_label(page, label, aside)
    page.parts.append('<div class="hp-group">%s</div>' % ''.join(rows))


def build_list(ops, docs, guides):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    if not ops:
        page.parts.append('<div class="hp-none">Forge\'s operations could not be read here.</div>')
    public = [op for op in ops if op.public]
    local = [op for op in ops if not op.public]
    add_section(page, 'OPERATIONS', '%d public' % len(public), [op_row(page, op) for op in public])
    add_section(page, 'FORGE DOCS', run_page.plural(len(docs), 'page'),
                [doc_row(page, doc) for doc in docs])
    add_section(page, 'LOCAL OPS', '%d installed' % len(local), [op_row(page, op) for op in local])
    add_section(page, 'GUIDES', run_page.plural(len(guides), 'guide'),
                [doc_row(page, doc) for doc in guides])
    page.parts.append('</div>')
    return page


# --- One page ---------------------------------------------------------------

def add_foot(page, copy_label, copy_text):
    """The end of a page: copy its bundle, or jump back to the top."""
    page.parts.append('<div class="av-buttons hp-foot">'
                      '<div class="av-button"%s>%s</div>'
                      '<div class="av-button" style="cursor:pointer" '
                      'onclick="window.scrollTo(0,0)">↑ Top</div></div>'
                      % (page.go(('copy_text', copy_text, 'Copied: run Forge to paste it')),
                         escape(copy_label)))


def add_back_row(page):
    """◀ Help on its own row at the top (the header's ◀ alone is too small
    and not obvious)."""
    page.parts.append('<div class="av-buttons"><div class="av-button"%s>◀ Help</div></div>'
                      % page.go(BACK))


def build_op(op):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    add_back_row(page)
    facts = ['core op' if op.public else 'local extension']
    if op.target:
        facts.append('target: ' + op.target)
    if op.body:
        facts.append('body: ' + op.body)
    blocks = [prose.heading(op.name, 1), prose.meta(' · '.join(facts))]
    if op.summary:
        blocks.append(prose.text(op.summary))
    if op.brief:
        blocks.append(prose.text(op.brief))
    if op.example:
        blocks += [prose.heading('Example', 3), prose.code('\n'.join(op.example), python=False)]
    if op.directives:
        blocks += [prose.heading('Directives', 3), prose.terms(op.directives)]
    if op.readme.strip():
        blocks.append(prose.heading('Reference', 2))
        blocks += markdown_blocks(op.readme, skip_title=op.name, shift=1)
    page.parts.append(prose.article(*blocks))
    add_foot(page, 'Copy help bundle', 'ENV: pythonista\nFORGE help %s full\n' % op.name)
    page.parts.append('</div>')
    return page


def build_doc(doc, text):
    page = cards.Page()
    page.parts.append('<div class="av-page">')
    add_back_row(page)
    if doc.kind == 'guide':
        where = 'Guide · library/guides/%s.md' % doc.name
        copy_label, copy_text = 'Copy guide bundle', 'ENV: pythonista\nMEMORY guide %s\n' % doc.name
    else:
        where = 'Forge doc · %s' % doc_source(doc)
        copy_label, copy_text = 'Copy doc bundle', 'ENV: pythonista\n%s\n' % doc_source(doc)
    blocks = [prose.heading(doc.title, 1), prose.meta(where)]
    if looks_like_markdown(text):
        blocks += markdown_blocks(text, skip_title=doc.title)
    else:
        blocks += renders.forge_text_blocks(text, limit=None)
    page.parts.append(prose.article(*blocks))
    add_foot(page, copy_label, copy_text)
    page.parts.append('</div>')
    return page


# --- Reading markdown -------------------------------------------------------

def looks_like_markdown(text):
    for line in str(text).splitlines()[:MARKDOWN_SNIFF_LINES]:
        if line.startswith('# ') or line.startswith('## '):
            return True
    return False


def next_is_code(lines, index):
    """Whether the next non-blank line after index is indented code."""
    for line in lines[index + 1:]:
        if line.strip():
            return line.startswith(CODE_INDENT)
    return False


def markdown_blocks(text, skip_title=None, shift=0):
    """Markdown as prose blocks: # headings (pushed down shift levels), - and
    1. bullets, Key: value terms, and code indented four spaces after a
    blank line. Blank lines inside code are kept, so a bundle example stays
    one block to copy. A level-1 heading equal to skip_title is dropped:
    the page already shows it."""
    lines = [line.rstrip().replace('\t', CODE_INDENT) for line in str(text).splitlines()]
    built = renders.ProseBuilder()
    for index, line in enumerate(lines):
        stripped = line.strip()
        level = len(stripped) - len(stripped.lstrip('#'))
        after_blank = index == 0 or not lines[index - 1].strip()
        term = renders.TERM_LINE.match(stripped)
        if not stripped:
            if built.kind == 'code' and next_is_code(lines, index):
                built.add('code', '')
            else:
                built.finish()
        elif line.startswith(CODE_INDENT) and (built.kind == 'code' or after_blank):
            built.add('code', line[len(CODE_INDENT):])
        elif 1 <= level <= 4 and stripped[level:level + 1] == ' ':
            words = stripped[level:].strip()
            if level == 1 and skip_title and words.lower() == str(skip_title).lower():
                built.finish()
            else:
                built.heading(words, min(level + shift, 4))
        elif stripped[:2] in ('- ', '* '):
            built.bullet('• ' + stripped[2:])
        elif renders.is_numbered(stripped):
            built.bullet(stripped)
        elif built.kind == 'bullet' and line[:1] == ' ':
            built.held.append(stripped)
        elif term and line[:1] != ' ':
            built.add('terms', term.groups())
        else:
            built.add('prose', stripped)
    return built.finished_blocks()