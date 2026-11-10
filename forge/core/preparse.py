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
from forge.core.parser import bundle_lines


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
    lines = bundle_lines(text)

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

    lines = bundle_lines(stripped)

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


# "FORGE rerun <stamp>" as the whole bundle replays that run's stored
# bundle, usually after repairing it in place with REPLACE. It is handled
# here, before parsing, so the replay is an ordinary new run with its own
# stamp and packet rather than a run nested inside another.
_RERUN_LINE = re.compile(r'^FORGE[ \t]+rerun(?:[ \t]+(\S+))?$')

# Only bundles refused at parse time are replayed: they ran nothing, so a
# replay cannot repeat work. A partly applied run is never replayed.
RERUNNABLE_STATUSES = ('FAILED_PARSE',)


def rerun_stamp(bundle_text):
    """
    Return the stamp named by a whole-bundle FORGE rerun line, else None.

    Returns '' for a rerun line with no stamp, so the caller can say so.
    """
    lines = [
        line
        for line in str(bundle_text or '').splitlines()
        if line.strip()
    ]
    if len(lines) != 1:
        return None
    match = _RERUN_LINE.match(lines[0].strip())
    if match is None:
        return None
    return match.group(1) or ''


def load_rerun_bundle(
    stamp,
    project_root=None,
    environment=None,
    mode='dev',
):
    """
    Return (bundle_text, bundle_app) for the stored bundle of run stamp.

    The stored text is the raw submission, so its own ENV: header and fence
    are removed here exactly as for a fresh bundle. Raises ValueError, with
    the next step, when the run cannot be replayed.
    """
    from forge.core import run_storage

    if not stamp:
        raise ValueError(
            'FORGE rerun needs a run stamp: FORGE rerun <stamp>. '
            'FORGE runs lists recent runs.'
        )

    stored = run_storage.read_text(
        project_root,
        stamp,
        'bundle.txt',
        mode=mode,
        environment=environment,
    )
    if stored is None or not stored.strip():
        raise ValueError(
            'No stored bundle for run %s. FORGE runs lists recent runs.'
            % stamp
        )

    text, bundle_app = take_env_header(stored)
    fenced = unwrap_fenced_bundle(text)
    if fenced is not None:
        text = fenced[0]
        if bundle_app is None:
            text, bundle_app = take_env_header(text)

    earlier = rerun_stamp(text)
    if earlier is not None:
        raise ValueError(
            'Run %s was itself FORGE rerun %s. Repair the bundle of run %s '
            'and send FORGE rerun %s.' % (stamp, earlier, earlier, earlier)
        )

    manifest, manifest_error = run_storage.read_manifest(
        project_root,
        stamp,
        mode=mode,
        environment=environment,
    )
    if manifest is None:
        raise ValueError(
            'Cannot replay run %s: %s' % (stamp, manifest_error)
        )
    status = manifest.get('status') or 'UNKNOWN'
    if status not in RERUNNABLE_STATUSES:
        raise ValueError(
            'Run %s finished %s. FORGE rerun replays only FAILED_PARSE runs, '
            'which ran nothing; send a fresh bundle instead.'
            % (stamp, status)
        )

    return text, bundle_app


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


# A placeholder in an alias expansion: $1, $2 ... (one word), $* (every
# word), $-1 (the last word) or $^ (every word but the last).
_ALIAS_PLACEHOLDER = re.compile(r'\$(\*|\^|-1|\d+)')


def substitute_alias_args(expansion, args_str):
    """Fill an alias expansion's placeholders from the words typed after it.

    Every placeholder is filled in one pass, so $10 is the tenth word (not
    the first followed by a 0) and a word that itself looks like a
    placeholder is never expanded again. A positional placeholder with no
    matching word becomes empty.
    """
    args_str = str(args_str or '').strip()

    if not args_str:
        if _ALIAS_PLACEHOLDER.search(expansion):
            raise ValueError('Alias requires arguments but none were supplied.')
        return expansion

    arg_list = args_str.split()

    def fill(match):
        name = match.group(1)
        if name == '*':
            return args_str
        if name == '-1':
            return arg_list[-1]
        if name == '^':
            return ' '.join(arg_list[:-1])
        index = int(name)
        return arg_list[index - 1] if 1 <= index <= len(arg_list) else ''

    return _ALIAS_PLACEHOLDER.sub(fill, expansion)


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

    lines = bundle_lines(stripped)

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
    mode='dev',
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

    stamp = rerun_stamp(working_text)
    if stamp is not None:
        working_text, stored_app = load_rerun_bundle(
            stamp,
            project_root=project_root,
            environment=environment,
            mode=mode,
        )
        report['rerun_of'] = stamp
        # The run whose bundle.txt holds the text this run executed, so
        # FORGE resume can find it again.
        report['bundle_origin'] = stamp
        if bundle_app is None:
            bundle_app = stored_app

    # "FORGE resume <stamp>" as the whole bundle carries on a partly
    # applied run from the operation that failed. See forge.core.resume.
    from forge.core import resume

    resume_of = resume.resume_stamp(working_text)
    if resume_of is not None and 'rerun_of' not in report:
        loaded = resume.load(
            resume_of,
            project_root=project_root,
            environment=environment,
            mode=mode,
        )
        working_text = loaded['text']
        report['resume_of'] = resume_of
        report['bundle_origin'] = loaded['origin']
        # Taken back out of the run by the runner: the operations that
        # already applied, for the engine to carry instead of executing.
        report['resume_carried'] = loaded['carried']
        if bundle_app is None:
            bundle_app = loaded['bundle_app']

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
