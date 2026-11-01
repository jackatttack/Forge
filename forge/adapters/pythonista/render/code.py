# -*- coding: utf-8 -*-
"""
forge_ui.renderer.code

Reusable syntax-highlighted code renderer for Forge UI.

This renderer is deliberately UI-independent:
- input: text + path/options
- output: HTML document string

A WebView wrapper lives separately in forge_ui.components.code_preview.
"""

from __future__ import print_function

import io
import os
import re
import token
import tokenize

try:
    from .html_base import escape, html_document, theme_dict
except ImportError:  # run directly as a script for its smoke test
    from html_base import escape, html_document, theme_dict


PY_KEYWORDS = set([
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else',
    'except', 'finally', 'for', 'from', 'global', 'if', 'import',
    'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise',
    'return', 'try', 'while', 'with', 'yield',
])

PY_BUILTINS = set([
    'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict',
    'set', 'tuple', 'open', 'bool', 'enumerate', 'zip', 'min', 'max',
    'sum', 'abs', 'isinstance', 'getattr', 'setattr', 'hasattr',
])


def _mark_query(escaped_text, query=''):
    """Highlight query inside already-escaped text."""
    q = (query or '').strip()
    if not q:
        return escaped_text

    try:
        pattern = re.escape(escape(q))
        return re.sub(
            pattern,
            lambda m: '<mark>%s</mark>' % m.group(0),
            escaped_text,
            flags=re.IGNORECASE,
        )
    except Exception:
        return escaped_text


def _token_class(tok_type, tok_text, expect_name_kind=None):
    """Return CSS token class for a Python token."""
    if tok_type == token.NAME:
        if tok_text in PY_KEYWORDS:
            return 'kw'
        if expect_name_kind == 'def':
            return 'fn'
        if expect_name_kind == 'class':
            return 'cls'
        if tok_text in ('self', 'super'):
            return 'self'
        if tok_text in PY_BUILTINS:
            return 'builtin'
    elif tok_type == token.STRING:
        return 'str'
    elif tok_type == token.NUMBER:
        return 'num'
    elif tok_type == tokenize.COMMENT:
        return 'com'
    elif tok_type == token.OP:
        return 'op'
    return ''


def _line_segments_from_tokens(text):
    """Tokenize whole text and return {line_no: [(start, end, css_class), ...]}.

    Whole-buffer tokenisation means triple-quoted/multiline strings are handled
    by Python's tokenizer rather than a fragile line-local scanner.
    """
    out = {}

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text or '').readline))
    except Exception:
        return out

    expect_name_kind = None

    for tok in tokens:
        tok_type = tok.type
        tok_text = tok.string
        srow, scol = tok.start
        erow, ecol = tok.end

        if tok_type in (
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.INDENT,
            tokenize.DEDENT,
        ):
            continue

        cls = _token_class(tok_type, tok_text, expect_name_kind)

        if tok_type == token.NAME:
            if tok_text == 'def':
                expect_name_kind = 'def'
            elif tok_text == 'class':
                expect_name_kind = 'class'
            elif expect_name_kind in ('def', 'class'):
                expect_name_kind = None
        elif tok_type not in (token.OP,):
            expect_name_kind = None

        if not cls:
            continue

        # Single line token.
        if srow == erow:
            out.setdefault(srow, []).append((scol, ecol, cls))
            continue

        # Multiline token, usually triple-quoted string.
        for row in range(srow, erow + 1):
            if row == srow:
                start = scol
                end = None
            elif row == erow:
                start = 0
                end = ecol
            else:
                start = 0
                end = None
            out.setdefault(row, []).append((start, end, cls))

    return out


def _highlight_python_code_fragment(text, query=''):
    """Small fallback highlighter for Python code fragments."""
    text = text or ''
    out = []
    pos = 0

    pattern = re.compile(
        r'\b[A-Za-z_][A-Za-z0-9_]*\b'
        r'|\b\d+(?:\.\d+)?\b'
        r'|==|!=|<=|>=|:=|->|\+=|-=|\*=|/=|//=|\*\*'
        r'|[+\-*/%=<>!&|^~:.,()[\]{}]'
    )

    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append(_mark_query(escape(text[pos:m.start()]), query))

        tok = m.group(0)
        cls = ''

        if tok in PY_KEYWORDS:
            cls = 'kw'
        elif tok in PY_BUILTINS:
            cls = 'builtin'
        elif re.match(r'^\d', tok):
            cls = 'num'
        elif re.match(r'^[+\-*/%=<>!&|^~:.,()[\]{}]+$', tok):
            cls = 'op'

        part = _mark_query(escape(tok), query)
        if cls:
            out.append('<span class="%s">%s</span>' % (cls, part))
        else:
            out.append(part)

        pos = m.end()

    if pos < len(text):
        out.append(_mark_query(escape(text[pos:]), query))

    return ''.join(out)


def _highlight_python_line_fallback(line, query=''):
    """Conservative Python highlighting for invalid/partial code slices."""
    line = line or ''
    out = []
    code_buf = []
    i = 0
    n = len(line)

    def flush_code():
        if code_buf:
            out.append(_highlight_python_code_fragment(''.join(code_buf), query=query))
            del code_buf[:]

    while i < n:
        ch = line[i]

        if ch == '#':
            flush_code()
            out.append('<span class="com">%s</span>' % _mark_query(escape(line[i:]), query))
            return ''.join(out)

        if ch in ('"', "'"):
            flush_code()
            quote = ch
            triple = line[i:i + 3] == quote * 3
            j = i + (3 if triple else 1)
            escaped_char = False

            while j < n:
                if triple and line[j:j + 3] == quote * 3:
                    j += 3
                    break

                if not triple:
                    if escaped_char:
                        escaped_char = False
                    elif line[j] == '\\':
                        escaped_char = True
                    elif line[j] == quote:
                        j += 1
                        break

                j += 1

            out.append('<span class="str">%s</span>' % _mark_query(escape(line[i:j]), query))
            i = j
            continue

        code_buf.append(ch)
        i += 1

    flush_code()
    return ''.join(out)

def _highlight_python_code_fragment(text, query=''):
    """Small fallback highlighter for Python code fragments."""
    text = text or ''
    out = []
    pos = 0

    pattern = re.compile(
        r'\b[A-Za-z_][A-Za-z0-9_]*\b'
        r'|\b\d+(?:\.\d+)?\b'
        r'|==|!=|<=|>=|:=|->|\+=|-=|\*=|/=|//=|\*\*'
        r'|[+\-*/%=<>!&|^~:.,()[\]{}]'
    )

    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append(_mark_query(escape(text[pos:m.start()]), query))

        tok = m.group(0)
        cls = ''

        if tok in PY_KEYWORDS:
            cls = 'kw'
        elif tok in PY_BUILTINS:
            cls = 'builtin'
        elif re.match(r'^\d', tok):
            cls = 'num'
        elif re.match(r'^[+\-*/%=<>!&|^~:.,()[\]{}]+$', tok):
            cls = 'op'

        part = _mark_query(escape(tok), query)
        if cls:
            out.append('<span class="%s">%s</span>' % (cls, part))
        else:
            out.append(part)

        pos = m.end()

    if pos < len(text):
        out.append(_mark_query(escape(text[pos:]), query))

    return ''.join(out)


def _highlight_python_line_fallback(line, query=''):
    """Conservative Python highlighting for invalid/partial code slices."""
    line = line or ''
    out = []
    code_buf = []
    i = 0
    n = len(line)

    def flush_code():
        if code_buf:
            out.append(_highlight_python_code_fragment(''.join(code_buf), query=query))
            del code_buf[:]

    while i < n:
        ch = line[i]

        if ch == '#':
            flush_code()
            out.append('<span class="com">%s</span>' % _mark_query(escape(line[i:]), query))
            return ''.join(out)

        if ch in ('"', "'"):
            flush_code()
            quote = ch
            triple = line[i:i + 3] == quote * 3
            j = i + (3 if triple else 1)
            escaped_char = False

            while j < n:
                if triple and line[j:j + 3] == quote * 3:
                    j += 3
                    break

                if not triple:
                    if escaped_char:
                        escaped_char = False
                    elif line[j] == '\\':
                        escaped_char = True
                    elif line[j] == quote:
                        j += 1
                        break

                j += 1

            out.append('<span class="str">%s</span>' % _mark_query(escape(line[i:j]), query))
            i = j
            continue

        code_buf.append(ch)
        i += 1

    flush_code()
    return ''.join(out)

def _highlight_python_lines(text, query=''):
    """Return highlighted HTML content for each source line.

    Full valid Python uses tokenize. Partial preview slices can start inside
    an indented block, so they may not be valid standalone Python. In that
    case, fall back to a conservative line-level highlighter.
    """
    lines = (text or '').splitlines()
    segments = _line_segments_from_tokens(text)

    if not segments:
        return [_highlight_python_line_fallback(line, query=query) for line in lines]

    rendered = []

    for idx, line in enumerate(lines, 1):
        segs = sorted(segments.get(idx, []), key=lambda x: (x[0], 999999 if x[1] is None else x[1]))
        pos = 0
        chunks = []

        for start, end, cls in segs:
            start = max(0, min(int(start or 0), len(line)))
            if end is None:
                end = len(line)
            else:
                end = max(start, min(int(end or 0), len(line)))

            if start > pos:
                chunks.append(_mark_query(escape(line[pos:start]), query))

            part = _mark_query(escape(line[start:end]), query)
            if part:
                chunks.append('<span class="%s">%s</span>' % (cls, part))

            pos = max(pos, end)

        if pos < len(line):
            chunks.append(_mark_query(escape(line[pos:]), query))

        rendered.append(''.join(chunks) if chunks else _highlight_python_line_fallback(line, query=query))

    return rendered

def _highlight_plain_lines(text, rel_path='', query=''):
    """Conservative highlighting for non-Python files."""
    lines = (text or '').splitlines()
    rendered = []

    low = (rel_path or '').lower()

    for line in lines:
        s = _mark_query(escape(line), query)

        if low.endswith(('.json', '.csv')):
            s = re.sub(r'(&quot;.*?&quot;)', r'<span class="str">\1</span>', s)
            s = re.sub(r'\b(\d+(?:\.\d+)?)\b', r'<span class="num">\1</span>', s)
        elif low.endswith(('.md', '.txt')):
            if line.lstrip().startswith('#'):
                s = '<span class="kw">%s</span>' % s

        rendered.append(s)

    return rendered


def render_code_inner(text, rel_path='', start_line=1, show_lines=True,
                      wrap=True, syntax=True, query='', active_line=None):
    """Return inner HTML rows for rendered code."""
    lines = (text or '').splitlines()

    if not lines:
        return '<div class="empty">No readable text.</div>'

    if syntax and (rel_path or '').lower().endswith('.py'):
        rendered_lines = _highlight_python_lines(text, query=query)
    elif syntax:
        rendered_lines = _highlight_plain_lines(text, rel_path=rel_path, query=query)
    else:
        rendered_lines = [_mark_query(escape(line), query) for line in lines]

    rows = []

    for offset, content in enumerate(rendered_lines):
        line_no = int(start_line or 1) + offset
        active = ' active' if active_line == line_no else ''

        if show_lines:
            rows.append(
                '<div class="code-row%s" id="L%d"><span class="ln">%04d</span><span class="code">%s</span></div>'
                % (active, line_no, line_no, content)
            )
        else:
            rows.append(
                '<div class="code-row%s" id="L%d"><span class="code noln">%s</span></div>'
                % (active, line_no, content)
            )

    return '\n'.join(rows)


def code_css(theme=None, wrap=True):
    """Return CSS for code rendering."""
    t = theme_dict(theme)
    wrap_css = 'pre-wrap' if wrap else 'pre'
    overflow_wrap = 'anywhere' if wrap else 'normal'
    word_break = 'break-word' if wrap else 'normal'

    return """
.wrap {
    padding: 0 0 28px 0;
}
.code-row {
    display: flex;
    align-items: flex-start;
    min-height: 18px;
    border-bottom: 1px solid rgba(255,255,255,0.025);
}
.code-row:nth-child(2n) {
    background: rgba(255,255,255,0.012);
}
.code-row.active {
    background: rgba(255, 159, 67, 0.13);
    box-shadow: inset 3px 0 0 %(accent)s;
}
.ln {
    display: inline-block;
    width: 52px;
    flex: 0 0 52px;
    padding: 1px 8px 0 0;
    box-sizing: border-box;
    color: %(faint)s;
    text-align: right;
    user-select: none;
}
.code {
    display: block;
    white-space: %(wrap_css)s;
    overflow-wrap: %(overflow_wrap)s;
    word-break: %(word_break)s;
    padding: 1px 12px 1px 8px;
    color: %(text)s;
    font-family: Menlo, Consolas, monospace;
}
.code.noln {
    padding-left: 14px;
}
.kw { color: #ff6b7a; font-weight: 650; }
.fn { color: #68D3C2; font-weight: 650; }
.cls { color: #68D3C2; font-weight: 750; }
.self { color: #68D3C2; }
.builtin { color: #68D3C2; }
.str { color: #FF9F43; }
.num { color: #B58CFF; }
.com { color: #777777; font-style: italic; }
.op { color: %(text)s; }
.empty {
    padding: 24px;
    color: %(muted)s;
    font-family: -apple-system, sans-serif;
}
""" % {
        'accent': t.get('accent', '#FF9F43'),
        'faint': t.get('faint', '#6D6257'),
        'text': t.get('text', '#F7EFE4'),
        'muted': t.get('muted', '#BFA88F'),
        'wrap_css': wrap_css,
        'overflow_wrap': overflow_wrap,
        'word_break': word_break,
    }


def render_code_html(text, rel_path='', start_line=1, show_lines=True,
                     wrap=True, syntax=True, font_size=13, query='',
                     active_line=None, theme=None, title='Code Preview'):
    """Return a full HTML document for syntax-highlighted source code."""
    inner = render_code_inner(
        text,
        rel_path=rel_path,
        start_line=start_line,
        show_lines=show_lines,
        wrap=wrap,
        syntax=syntax,
        query=query,
        active_line=active_line,
    )

    return html_document(
        inner,
        title=title or 'Code Preview',
        theme=theme,
        font_size=font_size,
        extra_css=code_css(theme=theme, wrap=wrap),
    )


def read_file_range(path, start=None, end=None, pad=0):
    """Read a text file range and return (text, actual_start_line)."""
    if not path or not os.path.exists(path):
        return '', 1

    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except Exception:
        return '', 1

    if start is None:
        return '\n'.join(lines), 1

    start = max(1, int(start or 1) - int(pad or 0))
    end = int(end or start)
    end = min(len(lines), end + int(pad or 0))

    chunk = lines[start - 1:end]
    return '\n'.join(chunk), start


def smoke_test():
    sample = '''# demo
class Thing(object):
    """Triple quoted docstring should be orange."""
    def run(self):
        text = """multi
line
string"""
        return text
'''
    html = render_code_html(sample, rel_path='demo.py', start_line=1)
    assert '<span class="cls">Thing</span>' in html
    assert '<span class="fn">run</span>' in html
    assert 'Triple quoted docstring' in html
    assert 'multi' in html
    print('renderer.code smoke OK')
    print('html bytes=%s' % len(html))


if __name__ == '__main__':
    smoke_test()
