# -*- coding: utf-8 -*-
"""
forge_ui.renderer.html_base

Shared HTML/CSS foundation for Forge UI renderers.
"""

from __future__ import print_function

try:
    import html
except Exception:
    import cgi as html


DEFAULT_THEME = {
    'background': '#11100f',
    'surface': '#17110C',
    'surface_2': '#21170E',
    'panel': '#24180F',
    'border': '#573B18',
    'text': '#F7EFE4',
    'muted': '#BFA88F',
    'faint': '#6D6257',
    'accent': '#FF9F43',
    'danger': '#FF5A5F',
    'success': '#62D26F',
    'cyan': '#68D3C2',
    'purple': '#B58CFF',
}


def escape(text):
    """HTML-escape text safely."""
    try:
        return html.escape(str(text or ''))
    except Exception:
        return str(text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def theme_dict(theme=None):
    """Return a plain renderer theme dict from a dict or ThemeProfile-like object."""
    base = dict(DEFAULT_THEME)

    if theme is None:
        return base

    if isinstance(theme, dict):
        base.update(theme)
        return base

    # Support Forge UI ThemeProfile objects.
    mapping = {
        'background': 'background',
        'surface': 'surface',
        'surface_2': 'surface_2',
        'panel': 'panel',
        'border': 'border',
        'text': 'text',
        'muted_text': 'muted',
        'accent': 'accent',
        'danger': 'danger',
        'success': 'success',
    }

    for attr, key in mapping.items():
        try:
            value = getattr(theme, attr)
            if value:
                base[key] = value
        except Exception:
            pass

    return base


def base_css(theme=None, font_size=13, extra_css=''):
    """Return shared CSS used by Forge HTML renderers."""
    t = theme_dict(theme)
    fs = int(font_size or 13)

    return """
html, body {
    margin: 0;
    padding: 0;
    background: %(background)s;
    color: %(text)s;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
    font-size: %(fs)dpx;
    line-height: 1.42;
    overflow-x: hidden;
    -webkit-text-size-adjust: none;
}
* {
    box-sizing: border-box;
}
.wrap {
    padding: 10px 0 28px 0;
}
.card {
    margin: 10px 12px;
    padding: 12px;
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 16px;
}
.muted {
    color: %(muted)s;
}
.faint {
    color: %(faint)s;
}
.accent {
    color: %(accent)s;
}
.success {
    color: %(success)s;
}
.danger {
    color: %(danger)s;
}
.chip {
    display: inline-block;
    margin: 3px 5px 3px 0;
    padding: 3px 7px;
    border-radius: 999px;
    border: 1px solid %(border)s;
    color: %(muted)s;
    background: %(surface_2)s;
    font-size: 0.85em;
    font-weight: 700;
}
mark {
    background: %(accent)s;
    color: #111111;
    border-radius: 4px;
    padding: 0 2px;
}
%(extra_css)s
""" % {
        'background': t['background'],
        'surface': t['surface'],
        'surface_2': t['surface_2'],
        'border': t['border'],
        'text': t['text'],
        'muted': t['muted'],
        'faint': t['faint'],
        'accent': t['accent'],
        'success': t['success'],
        'danger': t['danger'],
        'fs': fs,
        'extra_css': extra_css or '',
    }


def html_document(body, title='Forge Render', theme=None, font_size=13,
                  extra_css='', body_attrs=''):
    """Wrap body HTML in a complete document."""
    return """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=yes">
<meta charset="utf-8">
<title>%s</title>
<style>
%s
</style>
</head>
<body %s>
<div class="wrap">%s</div>
</body>
</html>""" % (
        escape(title),
        base_css(theme=theme, font_size=font_size, extra_css=extra_css),
        body_attrs or '',
        body or '',
    )
