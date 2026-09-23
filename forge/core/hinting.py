# -*- coding: utf-8 -*-
"""
Failure guidance for Forge.

There are two failure paths:

1. Execution/validation failures have a result and an op module.
2. Bundle parse failures happen before executable results exist.

Specific op HINTS remain the preferred guidance.

Every failed known op also receives a route back to current help syntax:

    FORGE help <OP>

Parse failures receive equivalent run-level recovery guidance.
"""


def _as_lines(value):
    if value is None:
        return []

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            str(v)
            for v in value
        ]

    return [
        str(value)
    ]


def _render_hint(
    key,
    hint,
):
    lines = []

    if isinstance(
        hint,
        dict,
    ):
        message = (
            hint.get(
                'message'
            )
            or str(
                key
            )
        )

        lines.append(
            'HINT: '
            + str(
                message
            )
        )

        why = hint.get(
            'why'
        )

        if why:
            lines.append(
                'WHY: '
                + str(
                    why
                )
            )

        example = _as_lines(
            hint.get(
                'example'
            )
        )

        if example:
            lines.append(
                'EXAMPLE:'
            )

            lines.extend(
                example
            )

        next_steps = _as_lines(
            hint.get(
                'next'
            )
        )

        if next_steps:
            lines.append(
                'NEXT:'
            )

            for step in next_steps:
                lines.append(
                    '- '
                    + str(
                        step
                    )
                )

        see = hint.get(
            'see'
        )

        if see:
            lines.append(
                'See: '
                + str(
                    see
                )
            )

        return '\n'.join(
            lines
        )

    return (
        'HINT: '
        + str(
            hint
        )
    )


def _op_name(
    op_module,
    result=None,
):
    result = (
        result
        or {}
    )

    name = str(
        result.get(
            'op'
        )
        or ''
    ).strip()

    if (
        name
        and name != '?'
    ):
        return name.upper()

    spec = getattr(
        op_module,
        'SPEC',
        {},
    ) or {}

    return str(
        spec.get(
            'name'
        )
        or ''
    ).strip().upper()


def _append_help(
    text,
    op_name,
):
    text = str(
        text
        or ''
    ).rstrip()

    op_name = str(
        op_name
        or ''
    ).strip().upper()

    if not op_name:
        return text

    command = (
        'FORGE help '
        + op_name
    )

    if command.lower() in text.lower():
        return text

    if text:
        text += '\n'

    return (
        text
        + 'HELP:\n'
        + command
    )


def _generic_result_hint(
    op_name,
    result,
):
    status = str(
        (result or {}).get(
            'status'
        )
        or 'FAILED'
    )

    message = str(
        (result or {}).get(
            'message'
        )
        or ''
    ).strip()

    lines = [
        'HINT: %s failed and no specific recovery hint matched.'
        % (
            op_name
            or 'This operation'
        ),
    ]

    if message:
        lines.append(
            'WHY: Forge reported: '
            + message
        )
    else:
        lines.append(
            'WHY: Forge returned status '
            + status
            + '.'
        )

    lines.extend([
        'NEXT:',
        '- Read the reported error and current project state before retrying.',
        '- Make the smallest correction that addresses the reported failure.',
    ])

    return '\n'.join(
        lines
    )

# Statuses Forge's engine produces for any op. Their hint does not depend
# on which op carried them, so they live here rather than in each op table.
ENGINE_STATUS_HINTS = {
    'SKIPPED_AFTER_FAILURE': {
        'message': 'Skipped because an earlier operation in this bundle failed.',
        'why': (
            'After a failed mutation, gate or assertion, Forge skips later '
            'mutations and RUNs so nothing builds on a broken step.'
        ),
        'next': [
            'Fix the first failure listed in Errors, then rerun this operation.',
        ],
    },
    'SKIPPED_STALE_READ': {
        'message': 'The file changed since the pinned version was seen.',
        'why': (
            'IF_VERSION refused the edit so it could not overwrite content '
            'the model has not read. The file was not touched.'
        ),
        'next': [
            'READ the file again and pin the version in the new header.',
            'Check that the planned edit still fits the current content.',
        ],
    },
}


def _matching_hints(hints, haystack, max_hints):
    """Render the op hints whose key appears in haystack, in table order."""
    rendered = []
    for key, hint in hints.items():
        needle = str(key).lower()
        if not needle or needle.startswith('_') or needle not in haystack:
            continue
        rendered.append(_render_hint(key, hint))
        if len(rendered) >= max_hints:
            break
    return rendered


def render_hints_for_result(
    op_module,
    result,
):
    """
    Return the recovery hint for a failed or skipped result, or ''.

    Matching runs in tiers so the most specific evidence wins:

    1. Engine statuses such as SKIPPED_AFTER_FAILURE use
       ENGINE_STATUS_HINTS, whatever the op.
    2. The op's HINTS keys are matched against the status and message,
       which describe what actually went wrong.
    3. Only if nothing matched there, the same keys are matched against
       the preview too. Captured output such as test names or script
       stdout can contain any word, so it must never outrank the message.

    Within a tier, keys are tried in table order, up to _max_hints.
    """
    status = str((result or {}).get('status') or '')

    if status == 'APPLIED':
        return ''

    op_name = _op_name(
        op_module,
        result=result,
    )

    engine_hint = ENGINE_STATUS_HINTS.get(status)
    if engine_hint:
        return _append_help(
            _render_hint(status, engine_hint),
            op_name,
        )

    hints = getattr(op_module, 'HINTS', {}) or {}

    try:
        max_hints = int(hints.get('_max_hints', 1))
    except Exception:
        max_hints = 1

    failure_text = '\n'.join([
        status,
        str((result or {}).get('message') or ''),
    ]).lower()

    full_text = '\n'.join([
        str((result or {}).get('op') or ''),
        failure_text,
        str((result or {}).get('preview') or ''),
    ]).lower()

    rendered = (
        _matching_hints(hints, failure_text, max_hints)
        or _matching_hints(hints, full_text, max_hints)
    )

    if rendered:
        text = '\n\n'.join(rendered).strip()
    else:
        text = _generic_result_hint(
            op_name,
            result,
        )

    return _append_help(
        text,
        op_name,
    )


def _value_after(
    text,
    prefix,
):
    prefix_upper = str(
        prefix
    ).upper()

    for line in str(
        text
        or ''
    ).splitlines():
        stripped = line.strip()

        if stripped.upper().startswith(
            prefix_upper
        ):
            return stripped[
                len(
                    prefix
                ):
            ].strip()

    return ''


def _parse_error_op(
    error,
):
    text = str(
        error
        or ''
    )

    op_name = _value_after(
        text,
        'OP:',
    )

    if op_name:
        return op_name.split(
            None,
            1,
        )[0].strip().upper()

    first = (
        text.splitlines()[0]
        if text.splitlines()
        else ''
    )

    words = first.replace(
        ':',
        ' ',
    ).split()

    for index, word in enumerate(
        words
    ):
        if (
            word.lower() == 'for'
            and index + 1 < len(
                words
            )
        ):
            candidate = words[
                index + 1
            ].strip()

            if (
                candidate
                and candidate.upper()
                == candidate
            ):
                return candidate

    return ''


def _parse_hint_text(
    error,
    op_name,
):
    text = str(
        error
        or ''
    )

    missing_directive = _value_after(
        text,
        'MISSING DIRECTIVE:',
    )

    invalid_directive = _value_after(
        text,
        'INVALID DIRECTIVE:',
    )

    body_mode = _value_after(
        text,
        'BODY MODE:',
    ).lower()

    if missing_directive:
        lines = [
            'HINT: %s bundle is missing a required directive.'
            % (
                op_name
                or 'This Forge'
            ),
            'WHY: Required directive: '
            + missing_directive,
        ]

    elif invalid_directive:
        lines = [
            'HINT: %s bundle contains an unsupported directive.'
            % (
                op_name
                or 'This Forge'
            ),
            'WHY: Unsupported directive: '
            + invalid_directive
            + '. The parser error lists the allowed directives.',
        ]

    elif body_mode == 'forbidden':
        lines = [
            'HINT: %s does not accept a body.'
            % (
                op_name
                or 'This operation'
            ),
            'WHY: Remove the unexpected body and use the operation syntax shown by Forge help.',
        ]

    elif body_mode == 'required':
        lines = [
            'HINT: %s requires a body.'
            % (
                op_name
                or 'This operation'
            ),
            'WHY: The operation contract requires structured body content.',
        ]

    elif (
        'Missing END_' in text
        or 'Missing end_' in text
    ):
        lines = [
            'HINT: A Forge structured block was not closed.',
            'WHY: The parser reached the end of the bundle before finding the required END marker.',
        ]

    elif op_name:
        lines = [
            'HINT: %s bundle syntax was rejected.'
            % op_name,
            'WHY: The complete bundle is parsed before execution, so no operations were run.',
        ]

    else:
        lines = [
            'HINT: Forge could not parse the submitted bundle.',
            'WHY: The complete bundle is parsed before execution, so no operations were run.',
        ]

    lines.append(
        'NEXT:'
    )

    lines.append(
        '- Read the parser error exactly before changing the bundle.'
    )

    lines.append(
        '- Do not guess Forge directives or syntax.'
    )

    if op_name:
        lines.append(
            '- FORGE help '
            + op_name
        )
    else:
        lines.append(
            '- FORGE ops'
        )

    return '\n'.join(
        lines
    )


def render_parse_hints(
    errors,
):
    output = []
    seen = set()

    for error in (
        errors
        or []
    ):
        text = str(
            error
            or ''
        ).strip()

        if not text:
            continue

        op_name = _parse_error_op(
            text
        )

        key = (
            op_name,
            text.splitlines()[0],
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        output.append({
            'op': (
                op_name
                or 'FORGE'
            ),
            'target': '?',
            'hint': _parse_hint_text(
                text,
                op_name,
            ),
        })

    return output