"""
Opt-in bundle controls: directives that let a bundle stop itself.

Forge behaves exactly as before unless a bundle asks for these.

STOP_ON_FAIL: yes
    On RUN, a non-zero exit stops every later mutation and RUN, exactly
    as a failed edit does. Without it, a failed RUN is only an observation.

Assertion directives (EXPECT_HITS on SEARCH)
    An op carrying an assertion always stops later mutations when the
    assertion fails. Asking a question and then ignoring the answer is
    never what a bundle means.
"""

import re


STOP_DIRECTIVE = 'STOP_ON_FAIL'

# Directives whose failure always stops later mutations.
ASSERTION_DIRECTIVES = ('EXPECT_HITS',)

TRUE_VALUES = ('yes', 'true', 'on', '1')

# "3", "=3", ">0", ">=2", "<5", "<=5"
_COUNT_PATTERN = re.compile(r'^\s*(>=|<=|>|<|=)?\s*(\d+)\s*$')


def requests_stop_on_failure(parsed_op):
    """Return True when this op asked for its own failure to stop the bundle."""
    directives = (parsed_op or {}).get('directives') or {}
    if str(directives.get(STOP_DIRECTIVE) or '').strip().lower() in TRUE_VALUES:
        return True
    return any(name in directives for name in ASSERTION_DIRECTIVES)


def parse_count_expectation(text):
    """
    Parse an expected count such as '0', '>0' or '<=5'.

    Returns (operator, number). Raises ValueError with a readable message
    for anything else.
    """
    match = _COUNT_PATTERN.match(str(text or ''))
    if not match:
        raise ValueError(
            'Expected a count such as 0, 3, >0, >=2, <5 or <=5; got %r' % text
        )
    return match.group(1) or '=', int(match.group(2))


def count_meets(count, expectation):
    """Return True when count satisfies an (operator, number) expectation."""
    operator, number = expectation
    return {
        '=': count == number,
        '>': count > number,
        '>=': count >= number,
        '<': count < number,
        '<=': count <= number,
    }[operator]