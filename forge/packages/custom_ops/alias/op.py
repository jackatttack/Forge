# -*- coding: utf-8 -*-
"""
ALIAS custom op.

Manage local Forge aliases.

This op stores aliases in forge/aliases.json and provides list/show/add/remove
commands. One-line alias expansion is handled by forge.core.preparse before the
normal bundle parser runs.
"""

import json
import os


SPEC = {
    'name': 'ALIAS',
    'target_kind': 'none',
    'body_mode': 'optional',
    'allowed_directives': set(['ARGS', 'HINTS', 'DESCRIPTION', 'PATH_HINTS']),
    'required_directives': set(),
}


HELP = {
    'summary': 'Manage local Forge aliases and one-line command shortcuts.',
    'subject': [
        'No subject required. Use same-line args, e.g. ALIAS list or ALIAS show boot.',
        'ARGS overrides same-line args when provided by the parser.',
    ],
    'minimal_example': [
        'ALIAS list',
        '',
        'ALIAS tags',
        '',
        'ALIAS show boot',
        '',
        'ALIAS add boot : forge',
        'DESCRIPTION: Daily Forge boot bundle',
        'HINTS: files ops',
        'BEGIN_BODY',
        'MAP .',
        'DEPTH: 2',
        '',
        'FORGE ops',
        'END_BODY',
        '',
        'ALIAS remove boot',
    ],
    'common_failures': [
        'Missing subcommand.',
        'Missing name for show / add / remove.',
        'No body provided for add.',
        'Alias name collides with a real op; real ops always win.',
    ],
    'safe_usage': [
        'Use ALIAS list before adding new aliases.',
        'Use lowercase alias names.',
        'Use tags to group aliases by workflow.',
        'Aliases only expand when the submitted bundle is a single line.',
    ],
    'related_ops': ['FORGE'],
}


HINTS = {
    '_max_hints': 1,

    'no alias named': {
        'message': 'The requested alias does not exist.',
        'why': 'ALIAS show/remove can only use names currently stored in the alias registry.',
        'example': [
            'ALIAS list',
            '',
            'ALIAS show boot',
        ],
        'next': [
            'Run ALIAS list to see the available names.',
            'Check the alias spelling before retrying.',
        ],
    },

    'usage': {
        'message': 'ALIAS needs a subcommand.',
        'why': 'The op manages aliases through list/show/add/remove/tags.',
        'example': [
            'ALIAS list',
            'ALIAS show boot',
            'ALIAS add boot : forge',
            'BEGIN_BODY',
            'FORGE ops',
            'END_BODY',
        ],
        'next': ['Choose list, tags, show, add, or remove.'],
    },
}


_SUBCOMMANDS = ('list', 'show', 'add', 'remove', 'tags')


def _project_root(ctx):
    environment = (
        (ctx or {}).get('environment')
        or {}
    )

    root = (
        environment.get('project_root')
        or (ctx or {}).get('project_root')
    )

    if not root:
        raise ValueError(
            'ALIAS requires an explicit project_root.'
        )

    return os.path.abspath(
        root
    )


def _aliases_path(project_root=None, environment=None):
    from forge.core.aliases import (
        aliases_path as shared_aliases_path,
    )

    return shared_aliases_path(
        environment=environment,
        project_root=project_root,
    )


def _load_aliases(project_root=None, environment=None):
    from forge.core.aliases import (
        load_aliases as shared_load_aliases,
    )

    return shared_load_aliases(
        environment=environment,
        project_root=project_root,
    )


def _save_aliases(
    project_root,
    aliases,
    environment=None,
):
    from forge.core.aliases import (
        save_aliases as shared_save_aliases,
    )

    return shared_save_aliases(
        aliases,
        environment=environment,
        project_root=project_root,
    )


def _all_tags(project_root, environment=None):
    aliases = _load_aliases(
        project_root,
        environment=environment,
    )

    counts = {}

    for entry in aliases.values():
        tag = (
            entry.get('tag')
            or 'untagged'
        )

        counts[tag] = (
            counts.get(tag, 0)
            + 1
        )

    return sorted(
        counts.items()
    )


def _aliases_by_tag(
    project_root,
    tag,
    environment=None,
):
    aliases = _load_aliases(
        project_root,
        environment=environment,
    )

    tag = str(
        tag
        or ''
    ).strip()

    return {
        name: entry
        for name, entry
        in aliases.items()
        if (
            entry.get('tag')
            or 'untagged'
        ) == tag
    }


def _set_alias(
    project_root,
    name,
    expansion,
    tag=None,
    args=None,
    description=None,
    path_hints=False,
    environment=None,
):
    aliases = _load_aliases(
        project_root,
        environment=environment,
    )

    entry = {
        'expansion': expansion,
        'tag': tag,
        'args': args or [],
        'description': (
            description
            or ''
        ),
    }

    if path_hints:
        entry['path_hints'] = True

    aliases[name] = entry

    _save_aliases(
        project_root,
        aliases,
        environment=environment,
    )


def _remove_alias(
    project_root,
    name,
    environment=None,
):
    aliases = _load_aliases(
        project_root,
        environment=environment,
    )

    if name not in aliases:
        return False

    del aliases[name]

    _save_aliases(
        project_root,
        aliases,
        environment=environment,
    )

    return True


def _parse_name_tag(text):
    text = str(text or '').strip()
    if ' : ' in text:
        name, tag = text.split(' : ', 1)
        return name.strip(), (tag.strip() or None)
    return text, None


def _known_op_names():
    try:
        from forge.core.registry import OPS_BY_NAME, discover_ops
        discover_ops()
        return set(str(k).upper() for k in OPS_BY_NAME.keys())
    except Exception:
        return set()


def validate(parsed_op):
    directives = (parsed_op or {}).get('directives') or {}
    raw_args = str(directives.get('ARGS') or '').strip()
    body = str((parsed_op or {}).get('body') or '')

    if not raw_args:
        return [
            'ALIAS requires a subcommand: %s'
            % ', '.join(_SUBCOMMANDS)
        ]

    parts = raw_args.split(None, 1)
    subcmd = parts[0]
    name = parts[1].strip() if len(parts) > 1 else ''

    if subcmd not in _SUBCOMMANDS:
        return [
            'Unknown subcommand %r. Must be one of: %s'
            % (
                subcmd,
                ', '.join(_SUBCOMMANDS),
            )
        ]

    if (
        subcmd in ('show', 'remove', 'add')
        and not name
    ):
        return [
            'ALIAS %s requires a name.'
            % subcmd
        ]

    if (
        subcmd == 'add'
        and not body.strip()
    ):
        return [
            'ALIAS add requires a body containing the expansion text.'
        ]

    return []


def execute(ctx, parsed_op, result):
    environment = (
        (ctx or {}).get('environment')
        or {}
    )

    directives = (
        (parsed_op or {}).get(
            'directives'
        )
        or {}
    )

    raw_args = str(
        directives.get('ARGS')
        or ''
    ).strip()

    hints_raw = str(
        directives.get('HINTS')
        or ''
    ).strip()

    desc = str(
        directives.get('DESCRIPTION')
        or ''
    ).strip()

    path_hints = str(
        directives.get('PATH_HINTS')
        or ''
    ).strip().lower() in (
        'yes',
        'true',
        '1',
        'on',
    )

    body = str(
        (parsed_op or {}).get('body')
        or ''
    ).strip()

    parts = raw_args.split(
        None,
        1,
    )

    subcmd = parts[0]

    name = (
        parts[1].strip()
        if len(parts) > 1
        else ''
    )

    project_root = _project_root(
        ctx
    )

    aliases_path = _aliases_path(
        project_root,
        environment=environment,
    )

    if subcmd == 'list':
        tag_filter = (
            name.strip()
            or None
        )

        aliases = (
            _aliases_by_tag(
                project_root,
                tag_filter,
                environment=environment,
            )
            if tag_filter
            else _load_aliases(
                project_root,
                environment=environment,
            )
        )

        if not aliases:
            result['status'] = 'APPLIED'
            result['message'] = (
                'No aliases found.'
            )
            result['data']['aliases_path'] = (
                aliases_path
            )
            return

        lines = []

        for (
            alias_name,
            entry,
        ) in sorted(
            aliases.items()
        ):
            expansion = (
                entry.get('expansion')
                or ''
            )

            tag = (
                entry.get('tag')
                or ''
            )

            alias_args = (
                entry.get('args')
                or []
            )

            preview = (
                expansion.splitlines()[0]
                if expansion
                else ''
            )[:60]

            tag_text = (
                ' [%s]' % tag
                if tag
                else ''
            )

            args_text = (
                ' {%s}'
                % ','.join(alias_args)
                if alias_args
                else ''
            )

            lines.append(
                '  %-20s%s%s  %s'
                % (
                    alias_name,
                    tag_text,
                    args_text,
                    preview,
                )
            )

        result['status'] = 'APPLIED'
        result['message'] = (
            'Aliases (%d):\n%s'
            % (
                len(aliases),
                '\n'.join(lines),
            )
        )
        result['data']['aliases_path'] = (
            aliases_path
        )
        return

    if subcmd == 'tags':
        tags = _all_tags(
            project_root,
            environment=environment,
        )

        if not tags:
            result['status'] = 'APPLIED'
            result['message'] = (
                'No aliases defined.'
            )
            result['data']['aliases_path'] = (
                aliases_path
            )
            return

        lines = [
            '  %-20s  %d'
            % (
                tag,
                count,
            )
            for tag, count
            in tags
        ]

        result['status'] = 'APPLIED'
        result['message'] = (
            'Tags:\n%s'
            % '\n'.join(lines)
        )
        result['data']['aliases_path'] = (
            aliases_path
        )
        return

    if subcmd == 'show':
        aliases = _load_aliases(
            project_root,
            environment=environment,
        )

        alias = aliases.get(
            name
        )

        if alias is None:
            result['status'] = (
                'FAILED_NOT_FOUND'
            )
            result['message'] = (
                'No alias named %r.'
                % name
            )
            return

        alias_args = (
            alias.get('args')
            or []
        )

        description = (
            alias.get('description')
            or ''
        )

        tag = (
            alias.get('tag')
            or ''
        )

        expansion = (
            alias.get('expansion')
            or ''
        )

        lines = [
            "Alias %r" % name,
        ]

        if tag:
            lines.append(
                'Tag:   %s'
                % tag
            )

        if alias_args:
            lines.append(
                'Hints: %s'
                % ', '.join(
                    alias_args
                )
            )

        if description:
            lines.append(
                'Desc:  %s'
                % description
            )

        lines.append('')
        lines.append(
            expansion
        )

        result['status'] = 'APPLIED'
        result['message'] = (
            '\n'.join(lines)
        )
        result['data']['aliases_path'] = (
            aliases_path
        )
        return

    if subcmd == 'add':
        alias_name, tag = (
            _parse_name_tag(
                name
            )
        )

        if not alias_name:
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                'ALIAS add requires a non-empty alias name.'
            )
            return

        if (
            alias_name.upper()
            in _known_op_names()
        ):
            result['status'] = (
                'FAILED_PARSE'
            )
            result['message'] = (
                '%r is a real op name — aliases cannot shadow ops.'
                % alias_name
            )
            return

        hints = (
            hints_raw.split()
            if hints_raw
            else []
        )

        _set_alias(
            project_root,
            alias_name,
            body,
            tag=tag,
            args=hints,
            description=desc,
            path_hints=path_hints,
            environment=environment,
        )

        notes = []

        if tag:
            notes.append(
                'tag: %s'
                % tag
            )

        if hints:
            notes.append(
                'hints: %s'
                % ', '.join(hints)
            )

        if desc:
            notes.append(
                'description set'
            )

        note = (
            ' — '
            + ', '.join(notes)
            if notes
            else ''
        )

        result['status'] = 'APPLIED'
        result['message'] = (
            'Alias %r saved (%d lines)%s.'
            % (
                alias_name,
                len(
                    body.splitlines()
                ),
                note,
            )
        )
        result['data']['aliases_path'] = (
            aliases_path
        )
        return



    if subcmd == 'remove':
        removed = _remove_alias(
            project_root,
            name,
            environment=environment,
        )

        if not removed:
            result['status'] = (
                'FAILED_NOT_FOUND'
            )
            result['message'] = (
                'No alias named %r.'
                % name
            )
            return

        result['status'] = 'APPLIED'
        result['message'] = (
            'Alias %r removed.'
            % name
        )
        result['data']['aliases_path'] = (
            aliases_path
        )
        return

    result['status'] = (
        'FAILED_PARSE'
    )
    result['message'] = (
        'Unhandled ALIAS subcommand: %s'
        % subcmd
    )
