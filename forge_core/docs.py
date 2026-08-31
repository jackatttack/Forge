# -*- coding: utf-8 -*-
"""
Small reboot docs registry.

Docs are plain .txt files under forge/docs.

Supported:
- # title
- ## sections
- [[doc_slug]] references
- ## RELATED with "- slug — note"
- @forge-bundle ... @end-forge-bundle blocks
"""

import os
import re
import time


DOC_ROOT = os.path.join('workspaces', 'forge_reboot', 'docs')


def docs_root(project_root):
    return os.path.join(project_root, DOC_ROOT)


def _slug_for_name(name):
    base = os.path.basename(str(name or ''))
    if '.' in base:
        base = base.rsplit('.', 1)[0]
    return base.strip()


def _candidate_slugs(slug):
    raw = str(slug or '').strip()
    out = []
    for item in (raw, raw.replace('-', '_'), raw.replace('_', '-')):
        if item and item not in out:
            out.append(item)
    return out


def path_for_slug(project_root, slug):
    root = docs_root(project_root)
    for candidate in _candidate_slugs(slug):
        path = os.path.join(root, candidate + '.txt')
        if os.path.isfile(path):
            return path
    return ''


def list_docs(project_root):
    root = docs_root(project_root)
    rows = []
    if not os.path.isdir(root):
        return rows

    try:
        names = os.listdir(root)
    except Exception:
        names = []

    for name in names:
        if not name.endswith('.txt') or name.startswith('.'):
            continue
        path = os.path.join(root, name)
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            mtime = 0
        rows.append({
            'slug': _slug_for_name(name),
            'path': path,
            'mtime': mtime,
        })

    rows.sort(key=lambda r: r.get('mtime') or 0, reverse=True)
    return rows


_SECTION_RE = re.compile(r'^(#{2,})\s+(.+)\s*$')
_TITLE_RE = re.compile(r'^#\s+([\w\-:]+)\s*$')


def _is_related(name):
    return str(name or '').strip().upper().startswith('RELATED')


def _parse_related(lines):
    out = []
    for line in lines or []:
        s = str(line or '').strip()
        if not s:
            continue
        if s.startswith(('- ', '* ')):
            s = s[2:].strip()

        slug = s
        note = ''
        for sep in (' — ', ' -- ', ' - '):
            if sep in s:
                slug, note = s.split(sep, 1)
                slug = slug.strip()
                note = note.strip()
                break

        if slug and re.match(r'^[\w\-:]+$', slug):
            out.append((slug, note))
    return out


def parse(text, fallback_title=''):
    title = str(fallback_title or '').strip()
    sections = []
    related = []

    current_name = None
    current_lines = []

    def flush():
        if current_name is None and not current_lines:
            return

        name = current_name or 'intro'
        cleaned = list(current_lines)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()

        if _is_related(name):
            related.extend(_parse_related(cleaned))
            return

        if cleaned or current_name:
            sections.append({'name': name, 'lines': cleaned})

    for line in str(text or '').splitlines():
        if _TITLE_RE.match(line):
            if not title:
                title = _TITLE_RE.match(line).group(1).strip()
            continue

        match = _SECTION_RE.match(line)
        if match:
            flush()
            current_name = match.group(2).strip()
            current_lines = []
            continue

        current_lines.append(line)

    flush()

    return {
        'title': title or str(fallback_title or 'doc'),
        'sections': sections,
        'related': related,
    }


def load_doc(project_root, slug):
    path = path_for_slug(project_root, slug)
    if not path:
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception:
        return None

    parsed = parse(text, fallback_title=slug)
    parsed['slug'] = str(slug or '').strip()
    parsed['path'] = path
    parsed['raw'] = text
    return parsed


def resolve(project_root, slug):
    doc = load_doc(project_root, slug)
    if doc is None:
        return 'miss', str(slug or '')
    return 'hit', doc


def bundle_blocks(project_root, slug):
    doc = load_doc(project_root, slug)
    raw = (doc or {}).get('raw') or ''
    blocks = []
    current = []
    in_bundle = False

    for line in raw.splitlines():
        stripped = line.strip()
        if not in_bundle and stripped.startswith('@forge-bundle'):
            in_bundle = True
            current = []
            continue

        if in_bundle and stripped == '@end-forge-bundle':
            blocks.append('\n'.join(current).rstrip() + '\n')
            in_bundle = False
            current = []
            continue

        if in_bundle:
            if line.startswith('    '):
                current.append(line[4:])
            elif line.startswith('\t'):
                current.append(line[1:])
            else:
                current.append(line)

    return blocks


def bundle_text(project_root, slug, index):
    blocks = bundle_blocks(project_root, slug)
    try:
        idx = int(index)
    except Exception:
        idx = -1
    if idx < 0 or idx >= len(blocks):
        return ''
    return blocks[idx]


def relative_time(mtime):
    if not mtime:
        return ''
    delta = int(time.time() - float(mtime))
    if delta < 60:
        return '%d sec ago' % delta
    mins = delta // 60
    if mins < 60:
        return '%d min ago' % mins
    hrs = mins // 60
    if hrs < 24:
        return '%d hr ago' % hrs
    days = hrs // 24
    return '%d days ago' % days