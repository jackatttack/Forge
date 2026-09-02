# -*- coding: utf-8 -*-
"""
Small source editing helpers for Forge.

Keep this boring and testable. AST ops should resolve exact line ranges first,
then use these helpers for text replacement/insertion.
"""

import textwrap


def line_indent(line):
    s = line or ''
    return s[:len(s) - len(s.lstrip(' \t'))]


def replace_line_range(source_text, start_line, end_line, new_body):
    """
    Replace a 1-based inclusive line range with new_body.

    The replacement is dedented first, then re-indented to match the first
    line of the replaced range. This mirrors Forge2's useful AST patching feel.
    """
    lines = (source_text or '').splitlines(True)

    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise ValueError(
            'Invalid line range %d-%d for %d-line source'
            % (start_line, end_line, len(lines))
        )

    before = lines[:start_line - 1]
    after = lines[end_line:]

    indent = line_indent(lines[start_line - 1])
    block = textwrap.dedent((new_body or '').strip('\n'))

    new_lines = []
    for line in block.splitlines():
        if line.strip():
            new_lines.append(indent + line + '\n')
        else:
            new_lines.append('\n')

    if not new_lines:
        new_lines = ['\n']

    return ''.join(before) + ''.join(new_lines) + ''.join(after)


def insert_after_line(source_text, line_no, insert_body, indent='', tight=False):
    """
    Insert insert_body after 1-based line_no.

    line_no may be 0 to insert at the very start of the file.
    """
    src_lines = (source_text or '').splitlines(True)

    if line_no < 0 or line_no > len(src_lines):
        raise ValueError(
            'Invalid insert position after line %d in %d-line source'
            % (line_no, len(src_lines))
        )

    block = textwrap.dedent((insert_body or '').strip('\n'))

    new_lines = []
    for line in block.splitlines():
        if line.strip():
            new_lines.append((indent or '') + line + '\n')
        else:
            new_lines.append('\n')

    if not new_lines:
        return source_text or ''

    before = src_lines[:line_no]
    after = src_lines[line_no:]

    if not tight:
        if before and before[-1].strip():
            new_lines.insert(0, '\n')
        if after and after[0].strip():
            new_lines.append('\n')

    return ''.join(before) + ''.join(new_lines) + ''.join(after)


def insert_after_lines(source_text, line_no, insert_body, indent='', tight=False):
    """
    Compatibility alias: same behaviour as insert_after_line.
    """
    return insert_after_line(source_text, line_no, insert_body, indent=indent, tight=tight)
