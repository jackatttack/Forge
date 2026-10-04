# -*- coding: utf-8 -*-
"""
Near-miss guidance for exact-match failures.

When an exact OLD block matches nothing, the next question is always
"where is the text I meant, and what is different about it?". Answering
that inside the failure saves a READ round trip.

closest_block() finds the run of file lines most similar to the wanted
text. describe_closest() turns that into the lines a packet shows.
format_line_numbers() lists match positions compactly for ambiguity
failures such as a repeated ANCHOR.
"""

import difflib


# Editable: below this similarity a "closest" block is noise, not help.
MIN_SIMILARITY = 0.6

# Editable: files longer than this are not scanned, so failures stay fast.
MAX_LINES_SCANNED = 5000

# Editable: longest shown line (as repr) before it is shortened.
MAX_SHOWN_LINE = 120

# Editable: most line numbers listed before "(+N more)".
MAX_LISTED_LINES = 8


def format_line_numbers(line_numbers):
    """Return 'line 3' or 'lines 3, 9', shortened after MAX_LISTED_LINES."""
    numbers = [str(number) for number in line_numbers]
    if not numbers:
        return 'no lines'

    shown = numbers[:MAX_LISTED_LINES]
    text = ', '.join(shown)
    hidden = len(numbers) - len(shown)
    if hidden:
        text += ' (+%d more)' % hidden

    return ('line ' if len(numbers) == 1 else 'lines ') + text


def closest_block(text, wanted):
    """
    Find the run of file lines most similar to wanted.

    Returns a dict with start and end (1-based, inclusive), similarity
    (0 to 1) and difference, or None when the file is empty or too long
    to scan. difference is (line_number, wanted_line, file_line) for the
    first line that differs; file_line is None past the end of the file.
    """
    file_lines = str(text or '').splitlines()
    wanted_lines = str(wanted or '').splitlines() or ['']

    if not file_lines or len(file_lines) > MAX_LINES_SCANNED:
        return None

    size = min(len(wanted_lines), len(file_lines))
    matcher = difflib.SequenceMatcher(None, autojunk=False)
    matcher.set_seq2('\n'.join(wanted_lines))

    best_ratio = -1.0
    best_start = 0
    for start in range(len(file_lines) - size + 1):
        matcher.set_seq1('\n'.join(file_lines[start:start + size]))
        # The cheap upper bounds skip most windows without a full compare.
        if matcher.real_quick_ratio() <= best_ratio:
            continue
        if matcher.quick_ratio() <= best_ratio:
            continue
        ratio = matcher.ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = start

    difference = None
    for offset, wanted_line in enumerate(wanted_lines):
        index = best_start + offset
        file_line = file_lines[index] if index < len(file_lines) else None
        if file_line != wanted_line:
            difference = (index + 1, wanted_line, file_line)
            break

    return {
        'start': best_start + 1,
        'end': best_start + size,
        'similarity': best_ratio,
        'difference': difference,
    }


def _shown(line):
    """repr() a line so tabs, trailing spaces and quotes are visible."""
    if line is None:
        return '(past the end of the file)'
    shown = repr(line)
    if len(shown) > MAX_SHOWN_LINE:
        shown = shown[:MAX_SHOWN_LINE - 3] + '...'
    return shown


def describe_closest(text, wanted, label='OLD'):
    """Return the packet lines that describe the block closest to wanted."""
    found = closest_block(text, wanted)

    if not found or found['similarity'] < MIN_SIMILARITY:
        return (
            'No block in the file is close to %s; it may have moved or '
            'been rewritten. READ the file again.' % label
        )

    lines = [
        'Closest: lines %d-%d (%d%% similar).' % (
            found['start'],
            found['end'],
            int(round(found['similarity'] * 100)),
        ),
    ]

    difference = found['difference']
    if difference:
        line_number, wanted_line, file_line = difference
        lines.append('First difference at line %d:' % line_number)
        lines.append('  %s:  %s' % (label, _shown(wanted_line)))
        lines.append('  file: %s' % _shown(file_line))

    return '\n'.join(lines)