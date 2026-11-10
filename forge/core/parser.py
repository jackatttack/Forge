# -*- coding: utf-8 -*-
"""
Tiny reboot bundle parser.

Design rule:
Forge should preserve current Forge command-language behaviour unless
we deliberately document a breaking change.

This parser handles:
- known op headers
- same-line target / ARGS
- directives
- structured blocks such as BEGIN_BODY / END_BODY
- package SPEC shape validation
"""

import re

from forge.core.registry import OP_SPECS


BLOCK_SPECS = {
    'BODY': {
        'begin': 'BEGIN_BODY',
        'end': 'END_BODY',
        'field': 'body',
        'single': True,
    },
    'OLD': {
        'begin': 'BEGIN_OLD',
        'end': 'END_OLD',
        'field': 'blocks',
        'single': True,
    },
    'NEW': {
        'begin': 'BEGIN_NEW',
        'end': 'END_NEW',
        'field': 'blocks',
        'single': True,
    },
}

_BEGIN_MARKERS = {}
for _name, _spec in BLOCK_SPECS.items():
    _BEGIN_MARKERS[_spec['begin']] = (_name, _spec)

# Inside an OLD or NEW block, a bare (column 0) marker belonging to the
# partner block almost always means a closer was missing or mistyped.
# Reading on would swallow the following operation into this block's
# text, and that operation would vanish from the packet. Refusing the
# bundle is the only safe answer. BODY is deliberately not covered:
# bodies may contain Forge syntax as data (see test_parser_contract).
PARTNER_MARKERS = {
    'OLD': ('BEGIN_NEW', 'END_NEW'),
    'NEW': ('BEGIN_OLD', 'END_OLD'),
}

# A tagged opener such as "BEGIN_BODY @fix" starts a block that closes only
# at "END_BODY @fix". Bare markers inside it are plain text, so a bundle can
# write or edit text that itself contains Forge markers (a stored bundle
# being repaired before FORGE rerun, Forge's own docs and tests).
# Tags are letters, digits, "_" and "-".
_TAGGED_BEGIN = re.compile(r'^(BEGIN_[A-Z]+)[ \t]+@([A-Za-z0-9_-]+)$')


def bundle_lines(text):
    """Split bundle text into lines at newlines only.

    str.splitlines() also breaks at form feeds, U+2028 and several other
    characters. Inside a body or an OLD block those are content: splitting
    there silently turned them into newlines, so a file was written, or a
    block matched, with text the bundle never contained. Only \\n, \\r\\n
    and \\r end a line here. A final newline does not add an empty line.
    """
    lines = str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def _match_begin_marker(line):
    """Return (block_name, block_spec, tag) for a block opener, else None.

    tag is '' for a bare opener such as BEGIN_BODY. Openers sit at column 0.
    """
    rstripped = line.rstrip()

    if rstripped in _BEGIN_MARKERS:
        block_name, block_spec = _BEGIN_MARKERS[rstripped]
        return block_name, block_spec, ''

    match = _TAGGED_BEGIN.match(rstripped)
    if match and match.group(1) in _BEGIN_MARKERS:
        block_name, block_spec = _BEGIN_MARKERS[match.group(1)]
        return block_name, block_spec, match.group(2)

    return None


def _closes_block(line, end_marker):
    """True when line is end_marker at column 0, ignoring trailing space.

    end_marker may carry a tag ("END_BODY @fix"); the space before the tag
    may be any run of spaces or tabs.
    """
    if line[:1].isspace():
        return False
    return line.split() == end_marker.split()


def _is_directive(line):
    if ':' not in line:
        return False
    key = line.split(':', 1)[0].strip()
    return bool(key) and key == key.upper() and ' ' not in key


def _match_op_header(line):
    if line and line[0] in (' ', '\t'):
        return None, None

    s = (line or '').strip()
    matches = []

    for op_name in OP_SPECS.keys():
        if s == op_name or s.startswith(op_name + ' '):
            matches.append(op_name)

    if not matches:
        return None, None

    matches.sort(key=len, reverse=True)
    op_name = matches[0]
    return op_name, s[len(op_name):].strip()


def _body_mode(spec):
    mode = str((spec or {}).get('body_mode') or 'forbidden').strip().lower()
    if mode == 'none':
        mode = 'forbidden'
    return mode


def _validate_shape(ops):
    errors = []

    for parsed_op in ops:
        op_name = parsed_op.get('op') or '?'
        directives = parsed_op.get('directives') or {}
        body = parsed_op.get('body') or ''
        spec = OP_SPECS.get(op_name) or {}

        allowed = set(spec.get('allowed_directives') or [])
        required = set(spec.get('required_directives') or [])

        for key in sorted(directives.keys()):
            if key not in allowed:
                errors.append(
                    'Directive not allowed for %s: %s\n'
                    'OP: %s\n'
                    'INVALID DIRECTIVE: %s\n'
                    'ALLOWED DIRECTIVES:\n%s' % (
                        op_name,
                        key,
                        op_name,
                        key,
                        '\n'.join('- ' + x for x in sorted(allowed)) if allowed else '- none',
                    )
                )

        for key in sorted(required):
            if key not in directives:
                errors.append(
                    'Missing required directive for %s: %s\n'
                    'OP: %s\n'
                    'MISSING DIRECTIVE: %s' % (
                        op_name,
                        key,
                        op_name,
                        key,
                    )
                )

        mode = _body_mode(spec)
        has_body = bool(body.strip())

        if mode == 'forbidden' and has_body:
            errors.append(
                'Unexpected body for %s\n'
                'OP: %s\n'
                'BODY MODE: forbidden' % (op_name, op_name)
            )

        if mode == 'required' and not has_body:
            errors.append(
                'Missing required body for %s\n'
                'OP: %s\n'
                'BODY MODE: required' % (op_name, op_name)
            )

    return errors


def _read_block(lines, i, block_name, block_spec, op_name, tag='', target=''):
    """Read one BEGIN_/END_ block whose opener is lines[i].

    Returns (next_index, text, error). A tagged block closes only at its own
    tagged end marker and skips the partner-marker check: the tag is the
    author saying the text is data, markers included.
    """
    end_marker = block_spec.get('end')

    if tag:
        end_marker = '%s @%s' % (end_marker, tag)
        partner_markers = ()
    else:
        partner_markers = PARTNER_MARKERS.get(block_name, ())

    begin_line = i + 1
    collected = []
    i += 1

    while i < len(lines) and not _closes_block(lines[i], end_marker):
        if lines[i].rstrip() in partner_markers:
            return i, None, (
                'Line %d: %s inside the %s block opened at line %d for %s\n'
                'WHY: %s was probably missing or mistyped, so this block '
                'would swallow the text after it, including any later '
                'operation.\n'
                'NEXT:\n'
                '- Close the %s block with %s on its own line.\n'
                '- If the file really contains this line, use a LINES: range '
                'REPLACE instead.\n'
                '- Or tag the block so markers inside it are plain text: '
                'BEGIN_%s @raw ... END_%s @raw.'
                % (
                    i + 1, lines[i].rstrip(), block_name, begin_line, op_name,
                    end_marker, block_name, end_marker,
                    block_name, block_name,
                )
            )
        collected.append(lines[i])
        i += 1

    if i >= len(lines):
        return i, None, _missing_end_message(
            collected, block_spec, end_marker, op_name, target, tag,
        )

    return i + 1, '\n'.join(collected).rstrip(), None


def _missing_end_message(collected, block_spec, end_marker, op_name,
                         target, tag):
    """
    Explain an unclosed block well enough to repair it in one REPLACE.

    Names the operation by its header, since a bundle may hold several of
    the same op, and quotes lines instead of numbering them: a stripped
    ENV: line shifts the parser's numbering away from the stored bundle.
    In a bare block the first operation header at column 0 is almost
    always where the end marker was lost. A tagged block holds Forge
    syntax as data on purpose, so no header is guessed there.
    """
    header = ('%s %s' % (op_name, target)).strip()
    lines = [
        'Missing %s for %s' % (end_marker, header),
        'WHY: the %s block under %s never closed, so it ran to the end of '
        'the bundle.' % (block_spec.get('begin'), header),
        'NEXT:',
    ]

    swallowed = ''
    if not tag:
        for line in collected:
            if not line[:1].isspace() and _match_op_header(line)[0]:
                swallowed = line.rstrip()
                break

    if swallowed:
        lines.append(
            '- %s probably belongs on its own line just before this line, '
            'which starts the next operation: %s' % (end_marker, swallowed)
        )
    elif tag:
        lines.append(
            '- A tagged block closes only at %s, exactly, at column 0.'
            % end_marker
        )
    else:
        lines.append(
            "- Add %s on its own line after the block's last content line."
            % end_marker
        )

    return '\n'.join(lines)


def parse_bundle(text):
    lines = bundle_lines(text)
    ops = []
    errors = []
    i = 0

    while i < len(lines):
        while i < len(lines) and not lines[i].strip():
            i += 1

        if i >= len(lines):
            break

        op_name, target = _match_op_header(lines[i])
        if not op_name:
            raw_header = (lines[i] or '').strip()
            token = (
                raw_header.split(None, 1)[0].upper()
                if raw_header
                else ''
            )

            replacement = ''

            if token:
                try:
                    from forge.core.language import replacement_for
                    replacement = replacement_for(token)
                except Exception:
                    replacement = ''

            if replacement:
                errors.append(
                    '%s is retired. Use %s instead.'
                    % (
                        token,
                        replacement,
                    )
                )
            else:
                errors.append(
                    'Expected known op header at line %d: %r'
                    % (
                        i + 1,
                        lines[i],
                    )
                )

            break

        i += 1
        directives = {}
        body_lines = []
        blocks = {}

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            next_op, _ = _match_op_header(line)

            if next_op:
                break

            opener = _match_begin_marker(line)
            if opener:
                block_name, block_spec, tag = opener
                i, block_text, err = _read_block(
                    lines, i, block_name, block_spec, op_name,
                    tag=tag, target=target,
                )
                if err:
                    errors.append(err)
                    break

                if block_spec.get('single') and block_name in blocks:
                    errors.append('Duplicate block for %s: %s' % (op_name, block_name))
                    break

                if block_spec.get('field') == 'body':
                    if body_lines:
                        errors.append('Duplicate body for %s' % op_name)
                        break
                    body_lines = block_text.split('\n') if block_text else []
                else:
                    blocks[block_name] = block_text

                continue

            if stripped and _is_directive(line):
                key, value = line.split(':', 1)
                key = key.strip()
                if key in directives:
                    # The second value used to replace the first without a
                    # word, so the op ran with a setting nobody reading
                    # the bundle could predict.
                    errors.append(
                        'Duplicate directive at line %d under %s: %s\n'
                        'WHY: %s was already set to %r for this operation.\n'
                        'NEXT:\n'
                        '- Keep one %s line.'
                        % (i + 1, op_name, key, key, directives[key], key)
                    )
                    break
                directives[key] = value.strip()
                i += 1
                continue

            if stripped:
                # Command level accepts only blank lines, known op headers,
                # directives, and block markers. Anything else is a mistake
                # the user needs to see.
                #
                # This line previously fell through into body_lines, which
                # meant a typo such as REPLCE was silently appended to the
                # PRECEDING operation's body, even after its END_BODY had
                # closed. The bundle then reported APPLIED while quietly
                # executing something the user never wrote. A packet that
                # misreports what ran defeats the point of the packet, so
                # unrecognised command-level text is now a parse error and
                # the whole bundle is refused.
                errors.append(
                    'Unrecognised line %d under %s: %r\n'
                    'WHY: outside BEGIN_/END_ blocks, Forge accepts only op '
                    'headers, DIRECTIVE: value lines, and blank lines.\n'
                    'NEXT:\n'
                    '- Wrap file or code content in BEGIN_BODY / END_BODY.\n'
                    '- Check the operation name for typos.\n'
                    '- Use FORGE ops for the current public language.'
                    % (
                        i + 1,
                        op_name,
                        line,
                    )
                )
                break

            i += 1

        if errors:
            # Stop at the first parse error. Carrying on from a broken spot
            # only adds follow-on errors that bury the real one.
            break

        spec = OP_SPECS.get(op_name) or {}

        # Same-line args compatibility:
        # HELP SURFACE -> HELP with ARGS: SURFACE
        # RUNS latest  -> RUNS with ARGS: latest
        if target and spec.get('target_kind') == 'none' and 'ARGS' not in directives:
            directives['ARGS'] = target
            target = ''

        ops.append({
            'op': op_name,
            'target': target or '',
            'directives': directives,
            'body': '\n'.join(body_lines).rstrip(),
            'blocks': blocks,
        })

    if not errors:
        errors.extend(_validate_shape(ops))

    return {
        'ops': ops,
        'errors': errors,
    }
