# -*- coding: utf-8 -*-
# SEARCH reboot op.
#
# Find text in files under a project-relative file or directory.
# Supports explicit QUERY plus readable inline forms:
# - SEARCH path FOR text
# - SEARCH text IN path
#
# Defaults are tuned for daily-driver use: source/doc extensions by default,
# noisy generated directories skipped, results grouped by file for scanning.

import os
import re

from forge.core.file_safety import safe_target, read_text


# Directories skipped during recursive walks by basename.
_SKIP_DIR_NAMES = set([
    '.git',
    '.Trash',
    '__pycache__',
    'artifacts',
    'site-packages',
    'site-packages-2',
    'site-packages-3',
    'stash',
    'stash_extensions',
    'snapshots',
    'forge2_runs',
    'patch_runs',
])

# Project-relative path suffixes skipped during walks. Catches Forge-generated
# run/branch/pack artifacts wherever they live in the package tree.
_SKIP_PATH_SUFFIXES = (
    ('artifacts', 'branches'),
    ('artifacts', 'runs'),
    ('artifacts', 'packed'),
    ('artifacts', 'runs_ephemeral'),
)

# Default extensions when EXT is not given. Source + common docs.
_DEFAULT_EXTS = ('.py', '.txt', '.md')

# EXT: all searches every extension. Without this, a search that finds
# nothing cannot be distinguished from a search that never looked, which
# is the most misleading answer a locator can give.
_EXT_ALL_TOKENS = ('all', '*', 'any')

# Skipped directory names that are never worth reporting. These are
# caches, vendored packages, and Forge's own artifacts: their absence
# from results tells the reader nothing. A skipped dot-directory such as
# .github IS worth reporting, because it may hold real project content.
_UNREPORTED_SKIP_DIRS = set(_SKIP_DIR_NAMES)


SPEC = {
    'name': 'SEARCH',
    'target_kind': 'path',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'QUERY', 'CASE', 'LIMIT', 'EXT',
        'MATCH', 'CONTEXT', 'FILTER', 'EXCLUDE', 'ACTIVE_ONLY',
        'DEFINES', 'CALLS', 'IMPORTS', 'ASSIGNS',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Search project files by text or Python AST structure.',
    'minimal_example': [
        'SEARCH forge FOR package contract',
        '',
        'SEARCH package contract IN forge',
        '',
        'SEARCH forge',
        'QUERY: package contract',
        '',
        'SEARCH forge FOR render hints',
        'MATCH: fuzzy',
        'CONTEXT: 3',
        '',
        'SEARCH forge FOR surface',
        'EXT: .py,.txt',
        'LIMIT: 40',
        '',
        'SEARCH . FOR workflow_dispatch',
        'EXT: all',
        '',
        'SEARCH forge',
        'MATCH: ast',
        'DEFINES: run_text',
        '',
        'SEARCH forge',
        'MATCH: ast',
        'CALLS: parse_bundle',
        '',
        'SEARCH forge',
        'MATCH: ast',
        'IMPORTS: forge.core.preparse',
        '',
        'SEARCH forge',
        'MATCH: ast',
        'ASSIGNS: SPEC',
        'CASE: yes',
        '',
        'SEARCH forge',
        'MATCH: ast',
        'CALLS: expand_bundle',
        'FILTER: forge/core',
    ],
}


HINTS = {
    '_max_hints': 1,
    'query': {
        'message': 'SEARCH needs a query or AST search directive.',
        'why': 'Text search needs text. AST search needs a structural directive such as DEFINES, CALLS, IMPORTS, or ASSIGNS.',
        'example': [
            'SEARCH forge FOR package contract',
            '',
            'SEARCH forge',
            'QUERY: package contract',
            '',
            'SEARCH forge',
            'MATCH: ast',
            'CALLS: parse_bundle',
        ],
        'next': [
            'Use SEARCH path FOR text for simple text searches.',
            'Use QUERY when the search text is long or awkward.',
            'Use MATCH: ast with DEFINES, CALLS, IMPORTS, or ASSIGNS for Python structure.',
            'Use EXT to widen the file types scanned.',
        ],
    },
    'no hits': {
        'message': 'SEARCH found no hits.',
        'why': 'The query may be too specific, the target too narrow, or the text/structure may not exist in scanned files.',
        'example': [
            'SEARCH forge FOR hint',
            'MATCH: fuzzy',
            '',
            'SEARCH hint IN forge',
            '',
            'SEARCH forge',
            'MATCH: ast',
            'CALLS: parse_bundle',
        ],
        'next': [
            'Try MATCH: fuzzy for token-based text matching.',
            'For AST search, try a shorter name such as parse_bundle instead of module.parse_bundle.',
            'Use CASE: yes only when exact case matters.',
            'Broaden EXT, e.g. EXT: .py,.txt,.md,.json',
            'Search a wider directory or remove FILTER.',
        ],
    },
    'match must be': {
        'message': 'SEARCH MATCH must be exact, fuzzy, regex, or ast.',
        'why': 'SEARCH supports text matching and Python AST structural matching.',
        'example': [
            'SEARCH forge FOR render hints',
            'MATCH: fuzzy',
            '',
            'SEARCH forge',
            'MATCH: ast',
            'CALLS: parse_bundle',
        ],
        'next': ['Use MATCH: exact, MATCH: fuzzy, MATCH: regex, or MATCH: ast'],
    },
}


def _as_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _truthy(value):
    return str(value or '').strip().lower() in ('1', 'yes', 'y', 'true', 'on')


def _describe_exts(exts):
    """Human-readable extension scope. exts of None means everything."""
    if exts is None:
        return 'all'
    return ','.join(sorted(exts))


def _exts_for_data(exts):
    """Machine-readable extension scope for result data."""
    if exts is None:
        return 'all'
    return sorted(exts)


def _scope_notes(exts, stats):
    """
    Describe what a search did NOT look at.

    Returns zero, one, or two lines. Silence when nothing was skipped:
    a search that read everything should not have to say so.
    """
    notes = []

    skipped_ext = int((stats or {}).get('skipped_ext') or 0)
    if skipped_ext and exts is not None:
        notes.append(
            'skipped: %d file%s by extension (searched %s — use EXT: all to widen)'
            % (
                skipped_ext,
                '' if skipped_ext == 1 else 's',
                _describe_exts(exts),
            )
        )

    skipped_dirs = sorted((stats or {}).get('skipped_dirs') or [])
    if skipped_dirs:
        notes.append('skipped dirs: ' + ', '.join(skipped_dirs))

    return notes


def _result_message(hits, searched, exts, stats):
    """
    One-line summary for the packet's ops list.

    Zero hits is the case that misleads, so the count of unread files
    rides along with it rather than living only in the preview.
    """
    text = '%d hits across %d files scanned' % (hits, searched)

    skipped_ext = int((stats or {}).get('skipped_ext') or 0)
    if skipped_ext and exts is not None:
        text += ', %d skipped by extension' % skipped_ext

    return text


def _parse_exts(value):
    """
    Parse the EXT directive into a set of extensions, or None for all.

    Returns None when the caller asked for every extension, which callers
    must treat as "do not filter" rather than "filter against nothing".
    """
    raw = str(value or '').strip()

    if not raw:
        return set(_DEFAULT_EXTS)

    if raw.strip().lower() in _EXT_ALL_TOKENS:
        return None

    out = set()
    for part in raw.replace(';', ',').split(','):
        item = part.strip().lower()
        if not item:
            continue
        if not item.startswith('.'):
            item = '.' + item
        out.add(item)

    return out or set(_DEFAULT_EXTS)

def _strip_wrapping_quotes(text):
    """Remove one simple pair of wrapping quotes from a search query."""
    text = str(text or '').strip()
    if len(text) >= 2:
        first = text[0]
        last = text[-1]
        if first == last and first in ('"', "'"):
            return text[1:-1].strip()
    return text


def _inline_target_query(target, directives):
    target = str(target or '').strip()
    directives = directives or {}

    explicit = _strip_wrapping_quotes(directives.get('QUERY') or '')
    if explicit:
        return target, explicit

    marker = ' FOR '
    if marker in target:
        left, _sep, right = target.partition(marker)
        return left.strip(), _strip_wrapping_quotes(right)

    marker = ' IN '
    if marker in target:
        left, _sep, right = target.rpartition(marker)
        return right.strip(), _strip_wrapping_quotes(left)

    return target, ''


def _normalize_ws(s):
    return ' '.join(s.split())


def _fuzzy_match(pattern, line):
    needle = _normalize_ws(pattern).lower()
    hay = _normalize_ws(line).lower()
    if not needle:
        return False
    tokens = [t for t in needle.split(' ') if t]
    return all(tok in hay for tok in tokens)

def _parse_csv(value):
    return [part.strip() for part in str(value or '').split(',') if part.strip()]


def _active_only_excludes(enabled):
    if not enabled:
        return []
    return [
        'archive/',
        'workspaces/forge2/',
        'workspaces/forge_reboot/',
        'workspaces/forge_public_release/',
        'packed/',
    ]


def _path_excluded(rel, exclude_terms):
    rel_norm = str(rel or '').replace('\\', '/')
    for term in exclude_terms or []:
        term = str(term or '').replace('\\', '/').strip()
        if term and term in rel_norm:
            return True
    return False


def _classify_text_hit(rel, line):
    rel_norm = str(rel or '').replace('\\', '/').lower()
    stripped = str(line or '').strip()
    code = stripped.lower()

    if rel_norm.endswith(('.md', '.txt', '.rst')):
        return 'doc'
    if '/smoke' in rel_norm or 'smoke' in rel_norm or '/test' in rel_norm or 'test_' in rel_norm:
        if 'assert' in code:
            return 'test_assertion'
        return 'test'
    if rel_norm.endswith('.py'):
        if code.startswith('#'):
            return 'comment'
        if code.startswith('def ') or code.startswith('async def '):
            return 'function'
        if code.startswith('class '):
            return 'class'
        if code.startswith('import ') or code.startswith('from '):
            return 'import'
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\s*=', stripped):
            return 'assignment'
        if '"' in stripped or "'" in stripped:
            return 'string_or_code'
        return 'code'
    return 'text'


def _suggest_read_for_hit(hit):
    rel = str((hit or {}).get('file') or '').strip()
    if not rel:
        return ''
    line = int((hit or {}).get('line') or 0)
    kind = str((hit or {}).get('kind') or '').strip()

    if (hit or {}).get('target'):
        return 'READ ' + str((hit or {}).get('target')).strip()

    if kind in ('function', 'class') and rel.endswith('.py'):
        return 'MAP ' + rel

    if line > 0:
        start = max(1, line - 8)
        end = line + 12
        return 'READ %s\nLINES: %d-%d' % (rel, start, end)

    return 'READ ' + rel


def _unique_suggested_reads(hits, limit=6):
    suggestions = []
    seen = set()
    for hit in hits or []:
        cmd = _suggest_read_for_hit(hit)
        if not cmd or cmd in seen:
            continue
        suggestions.append(cmd)
        seen.add(cmd)
        if len(suggestions) >= int(limit or 6):
            break
    return suggestions


def validate(parsed_op):
    errors = []
    raw_target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    target, query = _inline_target_query(raw_target, directives)

    if not target:
        errors.append('SEARCH requires a target file or directory')

    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    ast_terms = [
        str(directives.get('DEFINES') or '').strip(),
        str(directives.get('CALLS') or '').strip(),
        str(directives.get('IMPORTS') or '').strip(),
        str(directives.get('ASSIGNS') or '').strip(),
    ]

    if not query and match_mode != 'ast':
        errors.append('SEARCH requires QUERY or inline syntax: SEARCH path FOR text')

    if match_mode == 'ast' and not query and not any(ast_terms):
        errors.append('SEARCH MATCH: ast requires QUERY, DEFINES, CALLS, IMPORTS, or ASSIGNS')

    limit = _as_int(directives.get('LIMIT'), 80)
    if limit < 1:
        errors.append('SEARCH LIMIT must be >= 1')

    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    if match_mode not in ('exact', 'fuzzy', 'regex', 'ast'):
        errors.append('SEARCH MATCH must be exact, fuzzy, regex, or ast, got: ' + match_mode)

    context_raw = directives.get('CONTEXT')
    if context_raw not in (None, ''):
        context = _as_int(context_raw, -1)
        if context < 0:
            errors.append('SEARCH CONTEXT must be >= 0')
        elif context > 20:
            errors.append('SEARCH CONTEXT must be <= 20')

    return errors


def _should_skip_dir(root, dirpath, dirname):
    if dirname in _SKIP_DIR_NAMES:
        return True
    if dirname.startswith('.'):
        return True

    full = os.path.join(dirpath, dirname)
    try:
        rel = os.path.relpath(full, root)
    except Exception:
        return False

    parts = tuple(rel.replace('\\', '/').split('/'))
    for suffix in _SKIP_PATH_SUFFIXES:
        if len(parts) >= len(suffix) and parts[-len(suffix):] == suffix:
            return True

    return False


def _iter_files(root, abs_path, exts, stats=None):
    """
    Yield candidate files under abs_path.

    exts is a set of lowercase extensions, or None to accept every file.

    stats, when supplied, is a dict this function fills in so the caller
    can report what was NOT searched:
      skipped_ext   count of files excluded by the extension filter
      skipped_dirs  sorted names of dot-directories pruned from the walk

    Reporting the shape of the exclusion matters more than it looks: a
    caller that sees only "0 hits" will conclude the text is absent when
    it may simply never have been read.
    """
    if stats is None:
        stats = {}

    stats.setdefault('skipped_ext', 0)
    skipped_dirs = stats.setdefault('skipped_dirs', set())

    def accepted(path):
        if exts is None:
            return True
        return os.path.splitext(path)[1].lower() in exts

    if os.path.isfile(abs_path):
        if accepted(abs_path):
            yield abs_path
        else:
            stats['skipped_ext'] += 1
        return

    for dirpath, dirnames, filenames in os.walk(abs_path):
        kept = []
        for name in dirnames:
            if _should_skip_dir(root, dirpath, name):
                # Only surface pruned directories that might hold real
                # project content. Caches and vendored trees are noise.
                if name not in _UNREPORTED_SKIP_DIRS:
                    skipped_dirs.add(name)
                continue
            kept.append(name)

        dirnames[:] = kept

        for name in filenames:
            if name.startswith('.'):
                continue

            path = os.path.join(dirpath, name)
            if not accepted(path):
                stats['skipped_ext'] += 1
                continue

            yield path


def execute(ctx, parsed_op, result):
    raw_target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}
    target, query = _inline_target_query(raw_target, directives)

    root, abs_path, err = safe_target(ctx, target)
    if err:
        result['status'] = 'FAILED_INVALID_PATH'
        result['message'] = err
        return

    if not os.path.exists(abs_path):
        result['status'] = 'FAILED_NOT_FOUND'
        result['message'] = 'Target not found: ' + target
        return

    query = str(query or '').strip()
    case_sensitive = _truthy(directives.get('CASE'))
    limit = _as_int(directives.get('LIMIT'), 80)
    exts = _parse_exts(directives.get('EXT'))
    scan_stats = {}
    match_mode = str(directives.get('MATCH') or 'exact').strip().lower()
    context = _as_int(directives.get('CONTEXT'), 0)
    context = max(0, min(context, 20))
    path_filter = (directives.get('FILTER') or '').strip()
    exclude_terms = _parse_csv(directives.get('EXCLUDE'))
    exclude_terms.extend(_active_only_excludes(_truthy(directives.get('ACTIVE_ONLY'))))

    if match_mode == 'ast':
        from forge.core.ast_search import search_ast_files

        ast_exts = _parse_exts(directives.get('EXT') or '.py')
        files = []
        for path in _iter_files(root, abs_path, ast_exts, scan_stats):
            try:
                rel = os.path.relpath(path, root)
            except Exception:
                rel = path
            if path_filter and path_filter not in rel:
                continue
            if _path_excluded(rel, exclude_terms):
                continue
            files.append(path)

        criteria = {
            'defines': directives.get('DEFINES') or query,
            'calls': directives.get('CALLS') or '',
            'imports': directives.get('IMPORTS') or '',
            'assigns': directives.get('ASSIGNS') or '',
            'case_sensitive': case_sensitive,
        }

        hits, searched, syntax_errors, stopped_at_limit = search_ast_files(
            root,
            files,
            criteria,
            limit=limit,
        )

        files_hit = len(set([h.get('file') for h in hits]))
        header = [
            "SEARCH AST in %s [%d hit%s across %d Python file%s scanned, %d file%s hit]" % (
                target,
                len(hits), '' if len(hits) == 1 else 's',
                searched, '' if searched == 1 else 's',
                files_hit, '' if files_hit == 1 else 's',
            ),
        ]
        header.append('MATCH=ast')
        if criteria.get('defines'):
            header.append('DEFINES=%r' % criteria.get('defines'))
        if criteria.get('calls'):
            header.append('CALLS=%r' % criteria.get('calls'))
        if criteria.get('imports'):
            header.append('IMPORTS=%r' % criteria.get('imports'))
        if criteria.get('assigns'):
            header.append('ASSIGNS=%r' % criteria.get('assigns'))
        if path_filter:
            header.append('FILTER=%r' % path_filter)
        if exclude_terms:
            header.append('EXCLUDE=%r' % ','.join(exclude_terms))
        header.append('EXT=' + _describe_exts(ast_exts))
        header.extend(_scope_notes(ast_exts, scan_stats))
        header.append('LIMIT=%d' % limit)
        if stopped_at_limit:
            header.append('(limit reached, results may be incomplete)')
        if syntax_errors:
            header.append('syntax_errors=%d' % len(syntax_errors))

        out = ['\n'.join(header)]

        if not hits:
            out.append('(no hits)')
        else:
            grouped = {}
            for hit in hits:
                grouped.setdefault(hit.get('file'), []).append(hit)

            for rel in sorted(grouped):
                out.append(rel)
                for hit in grouped[rel]:
                    out.append(
                        '  >%04d: %-10s %-24s %s' % (
                            int(hit.get('line') or 0),
                            hit.get('kind') or '',
                            hit.get('name') or '',
                            hit.get('target') or '',
                        )
                    )
                    text = hit.get('text') or ''
                    if text:
                        out.append('         ' + text)

        result['status'] = 'APPLIED'
        result['message'] = '%d AST hits across %d files scanned' % (len(hits), searched)
        result['preview'] = '\n'.join(out)
        result['data'] = {
            'target': target,
            'query': query,
            'hits': hits,
            'searched': searched,
            'files_hit': files_hit,
            'limit': limit,
            'limit_reached': stopped_at_limit,
            'case_sensitive': case_sensitive,
            'match_mode': match_mode,
            'path_filter': path_filter,
            'exclude_terms': list(exclude_terms),
            'suggested_reads': _unique_suggested_reads(hits),
            'exts': _exts_for_data(ast_exts),
            'skipped_ext': int(scan_stats.get('skipped_ext') or 0),
            'skipped_dirs': sorted(scan_stats.get('skipped_dirs') or []),
            'syntax_errors': syntax_errors,
        }
        return

    # Compile regex up front so a bad pattern fails clean.
    regex = None
    if match_mode == 'regex':
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(query, flags)
        except re.error as e:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'Invalid regex: ' + str(e)
            return

    needle = query if case_sensitive else query.lower()

    grouped = {}        # rel_path -> {lineno: {'text': str, 'match': bool}}
    total_hits = 0
    searched = 0
    stopped_at_limit = False

    for path in _iter_files(root, abs_path, exts, scan_stats):
        try:
            rel = os.path.relpath(path, root)
        except Exception:
            rel = path

        if path_filter and path_filter not in rel:
            continue
        if _path_excluded(rel, exclude_terms):
            continue

        try:
            text = read_text(path)
        except Exception:
            continue

        searched += 1
        lines = text.splitlines()

        for idx, line in enumerate(lines):
            lineno = idx + 1

            if match_mode == 'regex':
                matched = regex.search(line) is not None
            elif match_mode == 'fuzzy':
                matched = _fuzzy_match(query, line)
            else:
                hay = line if case_sensitive else line.lower()
                matched = needle in hay

            if not matched:
                continue

            file_hits = grouped.setdefault(rel, {})

            if context:
                start = max(1, lineno - context)
                end = min(len(lines), lineno + context)
                for ctx_lineno in range(start, end + 1):
                    ctx_text = lines[ctx_lineno - 1].rstrip()
                    is_match = ctx_lineno == lineno
                    existing = file_hits.get(ctx_lineno)
                    if existing:
                        existing['match'] = existing.get('match', False) or is_match
                    else:
                        file_hits[ctx_lineno] = {'text': ctx_text, 'match': is_match}
            else:
                file_hits[lineno] = {'text': line.rstrip(), 'match': True}

            total_hits += 1
            if total_hits >= limit:
                stopped_at_limit = True
                break

        if stopped_at_limit:
            break

    files_hit = len(grouped)

    header = [
        "SEARCH %r in %s [%d hit%s across %d file%s scanned, %d file%s hit]" % (
            query,
            target,
            total_hits, '' if total_hits == 1 else 's',
            searched, '' if searched == 1 else 's',
            files_hit, '' if files_hit == 1 else 's',
        ),
    ]
    header.append('EXT=' + _describe_exts(exts))
    header.extend(_scope_notes(exts, scan_stats))
    header.append('MATCH=' + match_mode)
    if path_filter:
        header.append('FILTER=%r' % path_filter)
    if exclude_terms:
        header.append('EXCLUDE=%r' % ','.join(exclude_terms))
    header.append('LIMIT=%d' % limit)
    if context:
        header.append('CONTEXT=%d' % context)
    if stopped_at_limit:
        header.append('(limit reached, results may be incomplete)')

    out = ['\n'.join(header)]

    flat_hits = []
    if not grouped:
        out.append('(no hits)')
    else:
        for rel in sorted(grouped):
            out.append(rel)
            for lineno in sorted(grouped[rel]):
                item = grouped[rel][lineno]
                marker = '>' if item.get('match') else ' '
                kind = _classify_text_hit(rel, item.get('text', '')) if item.get('match') else ''
                label = (' [%s]' % kind) if kind and item.get('match') else ''
                out.append('  %s%04d:%s %s' % (marker, lineno, label, item.get('text', '')))
                if item.get('match'):
                    flat_hits.append({
                        'file': rel,
                        'line': lineno,
                        'text': item.get('text', ''),
                        'kind': kind,
                    })

    suggested_reads = _unique_suggested_reads(flat_hits)
    if suggested_reads:
        out.append('')
        out.append('Suggested next reads:')
        for cmd in suggested_reads:
            out.append('- ' + cmd.replace('\n', ' | '))

    result['status'] = 'APPLIED'
    result['message'] = _result_message(total_hits, searched, exts, scan_stats)
    result['preview'] = '\n'.join(out)
    result['data'] = {
        'target': target,
        'query': query,
        'hits': flat_hits,
        'searched': searched,
        'files_hit': files_hit,
        'limit': limit,
        'limit_reached': stopped_at_limit,
        'case_sensitive': case_sensitive,
        'match_mode': match_mode,
        'context': context,
        'path_filter': path_filter,
        'exclude_terms': list(exclude_terms),
        'suggested_reads': suggested_reads,
        'exts': _exts_for_data(exts),
        'skipped_ext': int(scan_stats.get('skipped_ext') or 0),
        'skipped_dirs': sorted(scan_stats.get('skipped_dirs') or []),
    }