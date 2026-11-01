"""Detail-card HTML for Forge Landing: what an op changed, syntax highlighted.

Pure text in, HTML out (no ui), built on the code renderer in
forge/adapters/pythonista/render/code.py.

    REPLACE  REMOVED (old lines, red) + IN FILE NOW (context, edit in green)
    INSERT   IN FILE NOW with the inserted lines in green
    WRITE    the written body
    READ     the lines read, in context
"""
import os

try:
    from ..render.code import code_css, read_file_range, render_code_inner
    from ..render.html_base import escape, html_document
except (ImportError, ValueError):   # landing imported as a top-level package
    from render.code import code_css, read_file_range, render_code_inner
    from render.html_base import escape, html_document

# --- Look -------------------------------------------------------------------
CONTEXT_LINES = 6
FONT_SIZE = 12
THEME = {   # Forge's live renderer palette in forge_ui's theme keys
    'background': '#151922', 'surface': '#151922', 'surface_2': '#1B2030',
    'panel': '#0D0F14', 'border': '#E91E63', 'text': '#EEF6FF',
    'muted': '#9FB4C9', 'faint': '#5C6B7E', 'accent': '#5AA9FF',
    'danger': '#FF5A5F', 'success': '#4CD964', 'cyan': '#5DEBFF',
    'purple': '#B58CFF',
}
EXTRA_CSS = '''
.section { font-family: Menlo, monospace; font-size: 11px; font-weight: bold;
  letter-spacing: 2px; color: #9FB4C9; margin: 14px 4px 6px; }
.section.removed-title { color: #FF5A5F; }
.section.added-title { color: #4CD964; }
.removed .code-row { background: rgba(255, 90, 95, 0.13); box-shadow: inset 3px 0 #FF5A5F; }
.code-row.hl { background: rgba(76, 217, 100, 0.13); box-shadow: inset 3px 0 #4CD964; }
'''
SCROLL_SCRIPT = ('<script>var hl = document.querySelector(".hl");'
                 'if (hl) { hl.scrollIntoView({block: "center"}); }</script>')


def section(title, css_class=''):
    return '<div class="section %s">%s</div>' % (css_class, escape(title))


def mark_lines(inner_html, first, last):
    """Tint rows first..last, using the L<n> row ids render_code_inner writes."""
    for number in range(first, last + 1):
        inner_html = inner_html.replace('<div class="code-row" id="L%d">' % number,
                                        '<div class="code-row hl" id="L%d">' % number)
    return inner_html


def old_text_of(row):
    for key, value in (row.parsed_op.get('blocks') or {}).items():
        if 'OLD' in str(key).upper():
            return str(value)
    return ''


def change_html(row, project_root):
    """HTML for the detail card's Change view, or None when there is nothing to show."""
    parts = []
    full_path = os.path.join(project_root, row.path) if row.path else None

    if row.op == 'REPLACE':
        old_text = old_text_of(row)
        if old_text:
            parts.append(section('REMOVED', 'removed-title'))
            parts.append('<div class="removed">%s</div>' % render_code_inner(
                old_text, rel_path=row.path or '', show_lines=False))

    if row.op in ('REPLACE', 'INSERT', 'READ') and full_path and row.start_line:
        text, first_line = read_file_range(full_path, row.start_line, row.end_line,
                                           pad=CONTEXT_LINES)
        if text:
            edited = row.op != 'READ'
            parts.append(section('IN FILE NOW  ·  LINES %d-%d' % (row.start_line, row.end_line),
                                 'added-title' if edited else ''))
            inner = render_code_inner(text, rel_path=row.path, start_line=first_line)
            if edited:
                inner = mark_lines(inner, row.start_line, row.end_line)
            parts.append('<div class="now">%s</div>' % inner)
    elif row.op == 'WRITE':
        body = str(row.parsed_op.get('body') or '')
        if body:
            parts.append(section('WRITTEN  ·  %d LINES' % len(body.splitlines()), 'added-title'))
            parts.append(render_code_inner(body, rel_path=row.path or row.target))

    if not parts:
        return None
    return html_document('\n'.join(parts) + SCROLL_SCRIPT, title=row.op, theme=THEME,
                         font_size=FONT_SIZE,
                         extra_css=code_css(theme=THEME, wrap=True) + EXTRA_CSS)