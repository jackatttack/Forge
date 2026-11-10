# -*- coding: utf-8 -*-
"""
Portable LLM-facing Forge packet renderer.

This module is part of the environment-independent Forge protocol.

It must not import Surface or any platform-specific integration.

Layout, top to bottom:

    === FORGE RUN ===   identity and status, then one line per fact the
                        reader acts on (Outcome, Repair, Resume, ...)
    === OPS ===         one numbered line per operation
    === FAILURE ===     only when something failed: each failure once,
                        with its fix steps
    === CHANGED ===     only when files changed
    === OUTPUT ===      only when operations produced something to read,
                        each block labelled with its operation

Rules the layout keeps:

- Each fact appears once. A failure's explanation lives under FAILURE; its
  OPS line carries only the status, and skipped operations carry no
  reason of their own.
- Everything refers to operations by their number in OPS.
- The first line and the Run, Mode, App and Status lines never change
  shape, so a tool can rely on them. FORGE runs reads OPS and CHANGED.
"""

import re


# ----- Editable settings ------------------------------------------------

# Fix steps shown per failure. An op's hint may offer more; the first few
# are the ones written for the common case.
MAX_FIX_STEPS = 4

# Ops whose preview only restates their OPS line (mode, counts, bytes).
# Such a preview is left out of OUTPUT. A preview with real content, such
# as landed lines, is always shown.
QUIET_OPS = ('WRITE', 'REPLACE', 'DELETE')


# ----- Fixed vocabulary -------------------------------------------------

APPLIED = 'APPLIED'

# Engine status for an op that never ran because an earlier one failed.
SKIPPED_AFTER_FAILURE = 'SKIPPED_AFTER_FAILURE'

# Section labels a rendered hint is made of (forge.core.hinting).
_HINT_HEADERS = (
    'HINT:', 'WHY:', 'RULE:', 'EXAMPLE:', 'DIRECTIVES:', 'NEXT:', 'HELP:',
    'See:',
)

# The fallback hint restates the error and adds only general advice.
_GENERIC_HINT = 'no specific recovery hint matched'

# Steps that apply to every refusal and so tell the reader nothing new.
_FILLER_STEPS = (
    'Read the parser error exactly before changing the bundle.',
    'Do not guess Forge directives or syntax.',
    'Change the operation so it satisfies this rule, then rerun it.',
)

_HELP_COMMAND = re.compile(r'^(FORGE (?:help [A-Z_]+(?: full)?|ops|bundle))\b')

# A preview line that is only a label and a value, or a byte count.
_SUMMARY_LINE = re.compile(
    r'^(?:[A-Za-z][A-Za-z _-]*: \S.*|\d+ bytes(?: written)?)$'
)


# ----- Changed files ----------------------------------------------------

def _packet_line_count(text):
    return len((text or '').splitlines())


def _packet_changed_ranges(before, after):
    before_lines = (before or '').splitlines()
    after_lines = (after or '').splitlines()
    max_len = max(len(before_lines), len(after_lines))
    nums = []

    for i in range(max_len):
        b = before_lines[i] if i < len(before_lines) else None
        a = after_lines[i] if i < len(after_lines) else None
        if b != a:
            nums.append(i + 1)

    if not nums:
        return 'none'

    return _number_ranges(nums)


def _packet_collect_touched(run):
    from forge.core.content_records import collect_changes
    touched = collect_changes(run)
    for item in touched:
        root = item.get('root') or ''
        relative = item['rel']
        item['shown'] = '%s:%s' % (root, relative) if root else relative
    return touched


def _format_changed_files(run):
    """Return the CHANGED section's lines, or [] when nothing changed."""
    touched = _packet_collect_touched(run)

    if not touched:
        return []

    lines = ['', '=== CHANGED ===']

    for item in touched:
        rel = item.get('shown') or item.get('rel') or '?'
        existed_before = bool(item.get('existed_before'))
        before = item.get('before') or ''
        after = item.get('after') or ''

        existed_after = bool(item.get('existed_after', True))

        from forge.core.content_records import state_content
        before_content = state_content(item, 'before')
        after_content = state_content(item, 'after')
        file_backed = any(
            content.get('encoding') == 'blob'
            for content in (before_content, after_content)
        )

        if file_backed:
            if not existed_before and not existed_after:
                action = 'created and removed'
            elif not existed_after:
                action = 'deleted'
            elif not existed_before:
                action = 'created'
            elif before_content['sha256'] == after_content['sha256']:
                action = 'touched, no content change'
            else:
                action = 'modified'
            summary = '%s · binary/large file · %d -> %d bytes' % (
                action, before_content['size'], after_content['size'],
            )
        elif not existed_before and not existed_after:
            summary = 'created and removed · no net change'
        elif not existed_after:
            summary = 'deleted · %d lines' % _packet_line_count(before)
        elif not existed_before:
            summary = 'created · %d lines' % _packet_line_count(after)
        elif before == after:
            summary = (
                'touched · %d lines · no content change'
                % _packet_line_count(after)
            )
        else:
            summary = (
                'modified · %d -> %d lines'
                % (
                    _packet_line_count(before),
                    _packet_line_count(after),
                )
            )

        lines.append('- %s — %s' % (rel, summary))

    return lines


def collapse_skip_errors(errors):
    """
    Return a run's error lines with repeated after-failure skips merged.

    Every op skipped after a failure records the same error apart from its
    op name. Real failures stay exactly as recorded; two or more skips
    become one line with a count, placed where the first skip was. The
    standard summary counts errors this way.
    """
    skip_prefix = SKIPPED_AFTER_FAILURE + ' |'
    skips = [err for err in errors if str(err).startswith(skip_prefix)]

    if len(skips) < 2:
        return list(errors)

    reason = str(skips[0]).split(' :: ', 1)[-1]
    merged = '%s | %s ops :: %s' % (SKIPPED_AFTER_FAILURE, len(skips), reason)

    collapsed = []
    for err in errors:
        if not str(err).startswith(skip_prefix):
            collapsed.append(err)
        elif merged not in collapsed:
            collapsed.append(merged)
    return collapsed


# ----- Small helpers ------------------------------------------------------

def _status(result):
    return str((result or {}).get('status') or 'UNKNOWN').strip().upper()


def _label(result):
    """'REPLACE app.py::main', or 'GIT upload' for a targetless op."""
    detail = result.get('target') or result.get('args') or ''
    return ('%s %s' % (result.get('op') or '?', detail)).strip()


def _number_ranges(numbers):
    """[2, 3, 4, 7] -> '2-4, 7'."""
    numbers = sorted(numbers)
    ranges = []
    start = prev = numbers[0]

    for number in numbers[1:]:
        if number == prev + 1:
            prev = number
            continue
        ranges.append((start, prev))
        start = prev = number
    ranges.append((start, prev))

    return ', '.join(
        str(a) if a == b else '%d-%d' % (a, b)
        for a, b in ranges
    )


def _brief_message(first_line, target):
    """Drop the target from an op's message: its OPS line already names it."""
    target = str(target or '')
    if len(target) < 4:
        return first_line
    for lead in (' in ', ' into ', ': ', ' '):
        needle = lead + target
        if needle in first_line:
            return first_line.replace(needle, '', 1)
    return first_line


# ----- Header -------------------------------------------------------------

def _outcome_line(results):
    """Counts and the first failure, for a run where something did not apply."""
    statuses = [_status(result) for result in results]
    if not statuses or all(status == APPLIED for status in statuses):
        return ''

    applied = statuses.count(APPLIED)
    skipped = len([s for s in statuses if s.startswith('SKIPPED')])
    failed = len(statuses) - applied - skipped
    first = next(
        number for number, status in enumerate(statuses, 1)
        if status != APPLIED
    )
    return (
        'Outcome: %d applied · %d failed · %d skipped · first failure at '
        'op %d of %d' % (applied, failed, skipped, first, len(statuses))
    )


def _header_lines(run, results):
    lines = ['=== FORGE RUN ===']

    if run.get('stamp'):
        lines.append('Run: ' + str(run.get('stamp')))

    lines.append('Mode: ' + str(run.get('mode') or 'dev'))

    if run.get('app'):
        lines.append('App: ' + str(run.get('app')))

    lines.append('Status: ' + str(run.get('status') or 'UNKNOWN'))

    outcome = _outcome_line(results)
    if outcome:
        lines.append(outcome)

    if run.get('env_warning'):
        lines.append('Warning: ' + str(run.get('env_warning')))

    if run.get('rerun_of'):
        lines.append('Rerun of: ' + str(run.get('rerun_of')))

    if run.get('repair'):
        lines.append('Repair: ' + str(run.get('repair')))

    if run.get('resume_of'):
        carried_count = int(run.get('resume_carried_count') or 0)
        if carried_count == 1:
            note = ' (op 1 applied there; not run again)'
        elif carried_count > 1:
            note = ' (ops 1-%d applied there; not run again)' % carried_count
        else:
            note = ''
        lines.append('Resume of: ' + str(run.get('resume_of')) + note)

    if run.get('resume'):
        lines.append('Resume: ' + str(run.get('resume')))

    # A bundle that ended with FORGE rerun or FORGE resume ran as two
    # runs; each packet says where it sits in the pair.
    if run.get('preceded_by'):
        lines.append(
            'Follows: %s (the run before it in this packet)'
            % run.get('preceded_by')
        )

    if run.get('follow_on'):
        if run.get('follow_on_skipped'):
            lines.append(
                'Follow-on: %s was not started, because this run did not '
                'apply' % run.get('follow_on')
            )
        else:
            lines.append(
                'Follow-on: %s (the next run in this packet)'
                % run.get('follow_on')
            )

    return lines


# ----- OPS ------------------------------------------------------------------

def _ops_lines(results):
    """One numbered line per operation.

    An applied op shows the first line of its message. A failed or skipped
    op shows only its status: the explanation is under FAILURE, once.
    """
    lines = []
    for number, result in enumerate(results, 1):
        status = _status(result)
        line = '%d. %s | %s | %s' % (
            number,
            status,
            result.get('op') or '?',
            result.get('target') or result.get('args') or '?',
        )

        message = str(result.get('message') or '').strip()
        if status == APPLIED and message:
            first_line, _, rest = message.partition('\n')
            line += ' :: ' + _brief_message(first_line, result.get('target'))
            if rest.strip():
                line += ' (continued in OUTPUT)'

        lines.append(line)
    return lines


# ----- FAILURE ----------------------------------------------------------------

def _hint_parts(hint_text):
    """Return what the packet shows from a rendered hint.

    {'steps': fix steps, 'directives': directive help lines, 'help': one
    FORGE help command}. A hint's opening line, reason and examples are
    left out: the failure's own message already says what went wrong.
    """
    text = str(hint_text or '')
    generic = _GENERIC_HINT in text
    steps, directives, help_command = [], [], ''
    section = ''

    for raw in text.splitlines():
        line = raw.strip()
        header = next(
            (name for name in _HINT_HEADERS if line.startswith(name)), '',
        )
        if header:
            section = header
            continue
        if not line:
            continue

        if section == 'HELP:':
            help_command = help_command or line
        elif section == 'DIRECTIVES:' and line.startswith('- '):
            directives.append(line[2:].strip())
        elif section == 'NEXT:' and line.startswith('- '):
            step = line[2:].strip()
            command = _HELP_COMMAND.match(step)
            if command:
                help_command = help_command or command.group(1)
            elif not generic and step not in _FILLER_STEPS:
                steps.append(step)

    return {
        'steps': steps[:MAX_FIX_STEPS],
        'directives': directives,
        'help': help_command,
    }


def _guidance_lines(parts):
    lines = []
    if parts['directives']:
        lines.append('Directives:')
        lines.extend('- ' + text for text in parts['directives'])
    if parts['steps']:
        lines.append('Fix:')
        lines.extend('- ' + step for step in parts['steps'])
    if parts['help']:
        lines.append('Help: ' + parts['help'])
    return lines


def _blocker_number(results):
    """The op whose failure caused the skips: the last failed op before the
    first skipped one. 0 when nothing was skipped."""
    statuses = [_status(result) for result in results]
    if SKIPPED_AFTER_FAILURE not in statuses:
        return 0
    first_skip = statuses.index(SKIPPED_AFTER_FAILURE) + 1
    for number in range(first_skip - 1, 0, -1):
        if statuses[number - 1] not in (APPLIED, SKIPPED_AFTER_FAILURE):
            return number
    return 0


def _failure_lines(results):
    """Each failed operation once: what went wrong, how to fix it, and
    which later operations were skipped because of it."""
    skipped = [
        number for number, result in enumerate(results, 1)
        if _status(result) == SKIPPED_AFTER_FAILURE
    ]
    blocker = _blocker_number(results)
    skipped_text = ''
    if skipped:
        skipped_text = '%s %s' % (
            'op' if len(skipped) == 1 else 'ops',
            _number_ranges(skipped),
        )

    lines = []
    for number, result in enumerate(results, 1):
        status = _status(result)
        if status in (APPLIED, SKIPPED_AFTER_FAILURE):
            continue

        if lines:
            lines.append('')
        lines.append('Op %d · %s · %s' % (number, _label(result), status))

        message = str(result.get('message') or '').strip()
        if message:
            lines.append(message)

        data = result.get('data')
        traceback_text = ''
        if isinstance(data, dict):
            traceback_text = str(data.get('traceback') or '').strip()
        if traceback_text:
            lines.append('Traceback (last lines):')
            lines.append(traceback_text)

        lines.extend(_guidance_lines(_hint_parts(result.get('hint'))))

        if _output_text(result):
            lines.append('Its output is under OUTPUT, op %d.' % number)

        if number == blocker and skipped_text:
            gate = str(result.get('gate') or '')
            lines.append(
                'Skipped because of it%s: %s.'
                % (' (%s gate)' % gate if gate else '', skipped_text)
            )

    if skipped_text and not blocker:
        lines.append('Skipped after an earlier failure: %s.' % skipped_text)

    return lines


def _refusal_lines(run, errors):
    """A bundle refused before execution: the errors, then where to look."""
    lines = ['Nothing ran: the bundle was refused before execution.']
    prefix = 'FAILED_PARSE | '

    for error in errors:
        text = str(error or '').strip()
        if text.startswith(prefix):
            text = text[len(prefix):]
        if text:
            lines.append('')
            lines.append(text)

    parts = {'steps': [], 'directives': [], 'help': ''}
    for hint in run.get('parse_hints') or []:
        if not isinstance(hint, dict):
            continue
        found = _hint_parts(hint.get('hint'))
        for key in ('steps', 'directives'):
            for item in found[key]:
                if item not in parts[key]:
                    parts[key].append(item)
        parts['help'] = parts['help'] or found['help']

    guidance = _guidance_lines(parts)
    if guidance:
        lines.append('')
        lines.extend(guidance)

    return lines


# ----- OUTPUT -----------------------------------------------------------------

def _is_summary_only(result, preview):
    """True when a quiet op's preview adds nothing to its OPS line."""
    if str(result.get('op') or '').upper() not in QUIET_OPS:
        return False
    return all(
        _SUMMARY_LINE.match(line)
        for line in preview.splitlines()[1:]
    )


def _output_text(result):
    """What one operation contributes to OUTPUT, or ''.

    The op's preview, unless it only restates the OPS line. An applied op's
    multi-line message (a PROJECTS brief, for example) is shown in full
    ahead of it; a failed op's message is under FAILURE instead.
    """
    status = _status(result)
    message = str(result.get('message') or '')
    preview = str(result.get('preview') or '').rstrip()

    if preview and status == APPLIED and _is_summary_only(result, preview):
        preview = ''

    if status == APPLIED and '\n' in message.strip():
        return message.rstrip() + ('\n' + preview if preview else '')
    return preview


def _output_lines(results):
    lines = []
    for number, result in enumerate(results, 1):
        text = _output_text(result)
        if not text:
            continue
        lines.append('--- op %d · %s ---' % (number, _label(result)))
        lines.append(text)
    return lines


# ----- The packet ---------------------------------------------------------------

def format_packet(run):
    """Return the complete deterministic AI-facing Forge packet."""
    run = run or {}
    results = run.get('results') or []
    errors = run.get('errors') or []

    lines = _header_lines(run, results)

    lines.append('')
    lines.append('=== OPS ===')
    lines.extend(_ops_lines(results) or ['(none)'])

    if results:
        failure = _failure_lines(results)
        if not failure and errors:
            failure = [str(error) for error in errors]
    elif errors:
        failure = _refusal_lines(run, errors)
    else:
        failure = []

    if failure:
        lines.append('')
        lines.append('=== FAILURE ===')
        lines.extend(failure)

    lines.extend(_format_changed_files(run))

    output = _output_lines(results)
    if output:
        lines.append('')
        lines.append('=== OUTPUT ===')
        lines.extend(output)

    return '\n'.join(lines).rstrip() + '\n'