# -*- coding: utf-8 -*-
"""
Pre-parse bundle transforms.

This layer runs before Forge's normal bundle parser. It must stay small,
boring, and explicit because mistakes here affect the language boundary.

Current policy:
- one whole-submission Markdown fence may wrap a bundle
- accepted fence labels are blank, forge, text, or plaintext
- prose outside a fence is never discarded
- aliases are command shortcuts, not macro expansion inside real bundles
- only a one-line submitted bundle can expand as an alias
- real op names always win
- aliases are loaded from the resolved <forge_home>/aliases.json
- an optional ENV: <app> first line names the app a bundle is meant for;
  it is removed before parsing and can only ever add a warning
"""

import json
import os
import re

from forge.core import app_identity


_ALLOWED_FENCE_LABELS = set([
    '',
    'forge',
    'text',
    'plaintext',
])


# An optional first line naming the app a bundle is meant for, for example
# "ENV: pythonide". Key and value are case-insensitive and whitespace is
# ignored, so "env : Python IDE" also matches.
_ENV_HEADER = re.compile(r'^\s*env\s*:\s*(\S.*?)\s*$', re.IGNORECASE)


def take_env_header(bundle_text):
    """
    Return (text_without_header, app_name) for an optional ENV: header.

    Only the first non-blank line can be the header. Without one, the text
    comes back unchanged with app_name None.
    """
    text = str(bundle_text or '')
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if not line.strip():
            continue
        match = _ENV_HEADER.match(line)
        if match is None:
            return bundle_text, None
        app_name = re.sub(r'\s+', '', match.group(1)).lower()
        remaining = lines[:index] + lines[index + 1:]
        return '\n'.join(remaining), app_name

    return bundle_text, None


def env_warning(bundle_app, running_app):
    """Return a warning for an ENV: header that does not fit, else ''.

    A mismatch only warns: the bundle still runs.
    """
    if bundle_app not in app_identity.KNOWN_APPS:
        return (
            'ENV: %s is not a known app (%s); Forge ran the bundle anyway.'
            % (bundle_app, ', '.join(app_identity.KNOWN_APPS))
        )
    if running_app != 'unknown' and bundle_app != running_app:
        return (
            'Bundle is marked ENV: %s but ran in %s.'
            % (bundle_app, running_app)
        )
    return ''


def unwrap_fenced_bundle(bundle_text):
    """
    Return (inner_text, label) for one whole-submission Markdown fence.

    This deliberately does not search for a bundle inside surrounding prose.
    Returning None leaves the original text for the strict parser to reject.
    """
    stripped = str(
        bundle_text
        or ''
    ).strip()

    lines = stripped.splitlines()

    if len(lines) < 3:
        return None

    opening = lines[0].strip()
    closing = lines[-1].strip()

    if not opening.startswith(
        '```'
    ):
        return None

    label = opening[
        3:
    ].strip().lower()

    if label not in _ALLOWED_FENCE_LABELS:
        return None

    if closing != '```':
        return None

    inner = '\n'.join(
        lines[
            1:-1
        ]
    )

    if not inner.strip():
        return None

    return inner, label


def aliases_path(project_root=None, environment=None):
    """Compatibility wrapper around canonical Forge alias storage."""
    from forge.core.aliases import (
        aliases_path as resolve_aliases_path,
    )

    return resolve_aliases_path(
        environment=environment,
        project_root=project_root,
    )


def load_aliases(project_root=None, environment=None):
    """Compatibility wrapper around canonical Forge alias storage."""
    from forge.core.aliases import (
        load_aliases as shared_load_aliases,
    )

    return shared_load_aliases(
        environment=environment,
        project_root=project_root,
    )


def known_op_names():
    try:
        from forge.core.registry import OPS_BY_NAME, discover_ops
        discover_ops()
        return set(str(k).upper() for k in OPS_BY_NAME.keys())
    except Exception:
        return set()


def alias_entry_parts(entry):
    if isinstance(entry, str):
        return entry, '', [], ''

    if not isinstance(entry, dict):
        return '', '', [], ''

    expansion = str(entry.get('expansion') or '')
    tag = str(entry.get('tag') or '')
    hints = entry.get('args') or []
    if not isinstance(hints, list):
        hints = []
    description = str(entry.get('description') or '')
    return expansion, tag, hints, description


def alias_info_bundle(name):
    return 'ALIAS show %s' % name


def substitute_alias_args(expansion, args_str):
    args_str = str(args_str or '').strip()

    if not args_str:
        if re.search(r'\$\d+', expansion) or '$*' in expansion or '$^' in expansion or '$-1' in expansion:
            raise ValueError('Alias requires arguments but none were supplied.')
        return expansion

    arg_list = args_str.split()
    last_arg = arg_list[-1] if arg_list else ''
    all_but_last = ' '.join(arg_list[:-1])

    out = expansion
    out = out.replace('$*', args_str)
    out = out.replace('$-1', last_arg)
    out = out.replace('$^', all_but_last)

    for idx, arg in enumerate(arg_list, 1):
        out = out.replace('$%d' % idx, arg)

    out = re.sub(r'\$\d+', '', out)
    out = out.replace('$*', '')
    out = out.replace('$^', '')
    out = out.replace('$-1', '')
    return out


def try_expand_alias(
    bundle_text,
    project_root=None,
    environment=None,
):
    stripped = str(
        bundle_text
        or ''
    ).strip()

    if not stripped:
        return None

    lines = stripped.splitlines()

    # Aliases are command shortcuts, not macro expansion inside real bundles.
    if len(lines) != 1:
        return None

    first_line = lines[0].strip()

    if not first_line:
        return None

    parts = first_line.split(
        None,
        1,
    )

    name = parts[0]

    args_str = (
        parts[1]
        if len(parts) > 1
        else ''
    )

    if name.upper() in known_op_names():
        return None

    aliases = load_aliases(
        project_root=project_root,
        environment=environment,
    )

    if name not in aliases:
        return None

    expansion, tag, hints, description = (
        alias_entry_parts(
            aliases.get(name)
        )
    )

    if not expansion.strip():
        return None

    if args_str.strip() in (
        '?',
        '??',
    ):
        return alias_info_bundle(
            name
        )

    return substitute_alias_args(
        expansion,
        args_str,
    )


def expand_bundle(
    bundle_text,
    project_root=None,
    environment=None,
):
    """Return (expanded_text, report).

    report is a small dict suitable for adding to the run object. It always
    names the running app (app); other keys appear only when something
    happened: an ENV: header (bundle_env, env_warning), an unwrapped fence,
    or an alias expansion.
    """
    report = {
        'app': app_identity.detect_app(),
    }

    # The header may sit above a fence or as the first line inside it.
    working_text, bundle_app = take_env_header(bundle_text)

    fenced = unwrap_fenced_bundle(
        working_text
    )

    if fenced is not None:
        working_text, label = fenced
        report[
            'unwrapped_markdown_fence'
        ] = (
            label
            or 'plain'
        )
        if bundle_app is None:
            working_text, bundle_app = take_env_header(working_text)

    if bundle_app is not None:
        report['bundle_env'] = bundle_app
        warning = env_warning(bundle_app, report['app'])
        if warning:
            report['env_warning'] = warning

    expanded = try_expand_alias(
        working_text,
        project_root=project_root,
        environment=environment,
    )

    if expanded is None:
        return (
            working_text,
            report,
        )

    original = str(
        working_text
        or ''
    ).strip()

    report.update({
        'expanded_from_alias': original,
        'expanded_bundle': expanded,
    })

    return (
        expanded,
        report,
    )
