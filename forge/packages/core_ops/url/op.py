# -*- coding: utf-8 -*-
"""
URL reboot op.

HTTP client for the reboot harness.

V1 supports:
- fetch: GET text content
- probe: HEAD request
- json: GET and parse JSON, optionally extracting JPATH
- download: GET binary/text content to project-relative DEST
"""

import json
import os
import re
import urllib.error
import urllib.request

from forge.core.file_safety import safe_target


SPEC = {
    'name': 'URL',
    'target_kind': 'url',
    'body_mode': 'forbidden',
    'allowed_directives': set([
        'CONFIRM',
        'DEST',
        'FOLLOW_REDIRECTS',
        'HEADERS',
        'JPATH',
        'MODE',
        'STRIP',
        'TIMEOUT',
    ]),
    'required_directives': set(),
}


HELP = {
    'summary': 'Fetch, probe, download, or parse HTTP resources.',
    'minimal_example': [
        'URL https://example.com',
        'MODE: fetch',
        '',
        'URL https://api.github.com/repos/python/cpython',
        'MODE: json',
        'JPATH: stargazers_count',
        '',
        'URL https://example.com/file.txt',
        'MODE: download',
        'DEST: downloads/file.txt',
    ],
    'common_failures': [
        'URL missing scheme.',
        'Unsupported MODE.',
        'download mode missing DEST.',
        'Network unavailable or endpoint rejected the request.',
        'JSON response could not be parsed.',
        'JPATH did not match the JSON shape.',
    ],
    'safe_usage': [
        'Use MODE: probe before fetching unknown endpoints.',
        'Use STRIP: markdown for compact LLM-readable pages.',
        'Use TIMEOUT to avoid slow requests blocking the loop too long.',
        'Use download mode only for files you intentionally want on disk.',
    ],
}


HINTS = {
    '_max_hints': 1,
    'target': {
        'message': 'URL needs a full http:// or https:// target.',
        'why': 'The reboot URL op must know which external resource to request.',
        'example': ['URL https://example.com', 'MODE: fetch'],
        'next': ['Add the full URL on the op line.', 'Use MODE: probe first if unsure.'],
    },
    'scheme': {
        'message': 'URL target must start with http:// or https://.',
        'why': 'Bare domains are ambiguous and unsafe for a low-friction command loop.',
        'example': ['URL https://example.com', 'MODE: probe'],
        'next': ['Add the scheme explicitly.'],
    },
    'mode': {
        'message': 'URL MODE must be fetch, probe, json, or download.',
        'why': 'The op needs a known response handling path.',
        'example': ['URL https://example.com', 'MODE: fetch'],
        'next': ['Pick one of the supported modes.'],
    },
    'dest': {
        'message': 'URL download mode needs DEST.',
        'why': 'Downloaded content must have a project-relative destination path.',
        'example': ['URL https://example.com/file.txt', 'MODE: download', 'DEST: downloads/file.txt'],
        'next': ['Add DEST or use MODE: fetch instead.'],
    },
    'timeout': {
        'message': 'URL request timed out or TIMEOUT was invalid.',
        'why': 'Network calls can stall the clipboard loop if not bounded.',
        'example': ['URL https://example.com', 'MODE: fetch', 'TIMEOUT: 20'],
        'next': ['Use a positive integer TIMEOUT.', 'Try MODE: probe before fetching.'],
    },
    'json': {
        'message': 'URL could not parse or extract the JSON response.',
        'why': 'The endpoint may not return JSON, or JPATH may not match the response shape.',
        'example': ['URL https://api.github.com/repos/python/cpython', 'MODE: json', 'JPATH: stargazers_count'],
        'next': ['Retry without JPATH to inspect the full JSON.', 'Check the endpoint returns JSON.'],
    },
    'http': {
        'message': 'The HTTP request failed.',
        'why': 'The server returned an error, the network failed, or the endpoint is unreachable.',
        'example': ['URL https://example.com', 'MODE: probe'],
        'next': ['Use MODE: probe.', 'Check the URL spelling and network connection.'],
    },
}


_TIMEOUT_DEFAULT = 20
_PREVIEW_LIMIT = 80


def validate(parsed_op):
    errors = []
    target = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    if not target:
        errors.append('URL requires target URL')
    elif not (target.startswith('http://') or target.startswith('https://')):
        errors.append('URL target must start with http:// or https://')

    mode = str(directives.get('MODE') or 'fetch').strip().lower()
    if mode not in ('fetch', 'probe', 'json', 'download'):
        errors.append('URL MODE must be fetch, probe, json, or download')

    strip_mode = str(directives.get('STRIP') or 'markdown').strip().lower()
    if strip_mode not in ('markdown', 'plain', 'no'):
        errors.append('URL STRIP must be markdown, plain, or no')

    if mode == 'download' and not str(directives.get('DEST') or '').strip():
        errors.append('URL download mode requires DEST')

    timeout_raw = str(directives.get('TIMEOUT') or _TIMEOUT_DEFAULT).strip()
    try:
        timeout = int(timeout_raw)
        if timeout < 1:
            errors.append('URL TIMEOUT must be >= 1')
    except Exception:
        errors.append('URL TIMEOUT must be an integer')

    return errors


def _truthy(value, default=True):
    raw = str(value if value is not None else '').strip().lower()
    if not raw:
        return bool(default)
    return raw in ('1', 'yes', 'y', 'true', 'on')


def _parse_headers(raw):
    headers = {}
    raw = str(raw or '').strip()
    if not raw:
        return headers

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value

    return headers


def _build_opener(follow_redirects):
    if follow_redirects:
        return urllib.request.build_opener()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(NoRedirect())


def _request(url, method, headers, timeout, follow_redirects):
    req = urllib.request.Request(url, method=method)
    req.add_header('User-Agent', 'Forge-Reboot-URL/0.1')
    for key, value in headers.items():
        req.add_header(key, value)

    opener = _build_opener(follow_redirects)
    return opener.open(req, timeout=timeout)


def _html_to_plain(text):
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.I | re.S)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.I | re.S)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _html_to_markdown(text):
    for tag in ('script', 'style', 'nav', 'header', 'footer', 'aside', 'form'):
        text = re.sub(r'<%s[^>]*>.*?</%s>' % (tag, tag), '', text, flags=re.I | re.S)

    lines = []

    for match in re.finditer(r'<h([1-3])[^>]*>(.*?)</h\1>', text, flags=re.I | re.S):
        level = int(match.group(1))
        value = _html_to_plain(match.group(2))
        if value:
            lines.append(('#' * level) + ' ' + value)

    for match in re.finditer(r'<p[^>]*>(.*?)</p>', text, flags=re.I | re.S):
        value = _html_to_plain(match.group(1))
        if value:
            lines.append(value)

    for match in re.finditer(r'<li[^>]*>(.*?)</li>', text, flags=re.I | re.S):
        value = _html_to_plain(match.group(1))
        if value:
            lines.append('- ' + value)

    if not lines:
        return _html_to_plain(text)

    return '\n\n'.join(lines).strip()


def _strip_text(text, mode):
    if mode == 'no':
        return text
    if mode == 'plain':
        return _html_to_plain(text)
    return _html_to_markdown(text)


def _jpath_get(obj, path):
    current = obj
    for part in str(path or '').split('.'):
        if not part:
            continue
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(part)
    return current


def _preview(title, body):
    lines = [title]
    body_lines = [line for line in str(body or '').splitlines()]
    if len(body_lines) > _PREVIEW_LIMIT:
        lines.extend(body_lines[:_PREVIEW_LIMIT])
        lines.append('... [%d more lines]' % (len(body_lines) - _PREVIEW_LIMIT))
    else:
        lines.extend(body_lines)
    return '\n'.join(lines).rstrip()


def _decode(data):
    return data.decode('utf-8', errors='replace')


def execute(ctx, parsed_op, result):
    url = (parsed_op.get('target') or '').strip()
    directives = parsed_op.get('directives') or {}

    mode = str(directives.get('MODE') or 'fetch').strip().lower()
    strip_mode = str(directives.get('STRIP') or 'markdown').strip().lower()
    timeout = int(str(directives.get('TIMEOUT') or _TIMEOUT_DEFAULT).strip())
    follow = _truthy(directives.get('FOLLOW_REDIRECTS'), default=True)
    headers = _parse_headers(directives.get('HEADERS'))
    jpath = str(directives.get('JPATH') or '').strip()
    dest_rel = str(directives.get('DEST') or '').strip()

    try:
        if mode == 'probe':
            with _request(url, 'HEAD', headers, timeout, follow) as resp:
                status = getattr(resp, 'status', None) or resp.getcode()
                content_type = resp.headers.get('Content-Type', '')
                content_length = resp.headers.get('Content-Length', 'unknown')
                final_url = getattr(resp, 'url', url)
                text = '\n'.join([
                    'Status: %s' % status,
                    'Content-Type: %s' % content_type,
                    'Content-Length: %s' % content_length,
                    'Final URL: %s' % final_url,
                ])

        elif mode == 'download':
            root, dest_abs, dest_err = safe_target(ctx, dest_rel)
            if dest_err:
                result['status'] = 'FAILED_INVALID_PATH'
                result['message'] = dest_err
                return

            with _request(url, 'GET', headers, timeout, follow) as resp:
                status = getattr(resp, 'status', None) or resp.getcode()
                content_type = resp.headers.get('Content-Type', '')
                final_url = getattr(resp, 'url', url)
                data = resp.read()

            parent = os.path.dirname(dest_abs)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)

            before = ''
            existed_before = os.path.exists(dest_abs)
            if existed_before and os.path.isfile(dest_abs):
                try:
                    with open(dest_abs, 'rb') as f:
                        before = f.read().decode('utf-8', errors='replace')
                except Exception:
                    before = ''

            with open(dest_abs, 'wb') as f:
                f.write(data)

            text = 'Downloaded %d bytes -> %s' % (len(data), dest_rel)
            result['touched'] = [{
                'rel': dest_rel,
                'before': before,
                'after': _decode(data),
                'existed_before': bool(existed_before),
                'kind': 'file',
            }]
            run = (ctx or {}).get('run') or {}
            run.setdefault('touched_files', []).extend(result['touched'])

        elif mode == 'json':
            with _request(url, 'GET', headers, timeout, follow) as resp:
                status = getattr(resp, 'status', None) or resp.getcode()
                content_type = resp.headers.get('Content-Type', '')
                final_url = getattr(resp, 'url', url)
                raw = _decode(resp.read())

            try:
                parsed = json.loads(raw)
                value = _jpath_get(parsed, jpath) if jpath else parsed
            except Exception as e:
                result['status'] = 'FAILED_PARSE'
                result['message'] = 'JSON/JPATH error: %s: %s' % (type(e).__name__, e)
                result['preview'] = _preview('URL %s [json failed]' % url, raw)
                return

            if isinstance(value, (dict, list)):
                text = json.dumps(value, indent=2, sort_keys=True)
            else:
                text = str(value)

        else:
            with _request(url, 'GET', headers, timeout, follow) as resp:
                status = getattr(resp, 'status', None) or resp.getcode()
                content_type = resp.headers.get('Content-Type', '')
                final_url = getattr(resp, 'url', url)
                raw = _decode(resp.read())
            text = _strip_text(raw, strip_mode)

    except urllib.error.HTTPError as e:
        result['status'] = 'FAILED_IO'
        result['message'] = 'HTTP %s: %s' % (e.code, e.reason)
        result['preview'] = 'URL %s\nError: %s' % (url, result['message'])
        return

    except Exception as e:
        result['status'] = 'FAILED_IO'
        result['message'] = '%s: %s' % (type(e).__name__, e)
        result['preview'] = 'URL %s\nError: %s' % (url, result['message'])
        return

    result['status'] = 'APPLIED'
    result['message'] = '%s %s' % (mode, status or 'ok')
    result['preview'] = _preview('URL %s [%s %s]' % (url, mode, status or 'ok'), text)
    result['data'] = {
        'url': url,
        'final_url': final_url,
        'mode': mode,
        'status_code': status,
        'content_type': content_type,
        'text': text,
        'dest': dest_rel or '',
    }
