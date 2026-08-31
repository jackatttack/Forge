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

from forge_core.registry import OP_SPECS


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


def _read_block(lines, i, block_name, block_spec, op_name):
    end_marker = block_spec.get('end')
    collected = []
    i += 1

    while i < len(lines) and lines[i].rstrip() != end_marker:
        collected.append(lines[i])
        i += 1

    if i >= len(lines):
        return i, None, 'Missing %s for %s' % (end_marker, op_name)

    return i + 1, '\n'.join(collected).rstrip(), None


def parse_bundle(text):
    lines = (text or '').splitlines()
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
            errors.append('Expected known op header at line %d: %r' % (i + 1, lines[i]))
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

            rstripped = line.rstrip()
            if rstripped in _BEGIN_MARKERS:
                block_name, block_spec = _BEGIN_MARKERS[rstripped]
                i, block_text, err = _read_block(lines, i, block_name, block_spec, op_name)
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
                    body_lines = block_text.splitlines()
                else:
                    blocks[block_name] = block_text

                continue

            if stripped and _is_directive(line):
                key, value = line.split(':', 1)
                directives[key.strip()] = value.strip()
                i += 1
                continue

            if stripped:
                body_lines.append(line)

            i += 1

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
