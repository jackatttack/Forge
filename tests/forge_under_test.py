# -*- coding: utf-8 -*-
"""
Decide and assert WHICH Forge these tests are exercising.

Forge is a runtime that can inspect and modify its own source, so a test
run that silently imports a different Forge than intended produces
believable nonsense. This module makes the choice explicit and loud.

Two intended modes, selected by FORGE_TEST_TARGET:

    checkout   (default)  import must come from this repository
    installed             import must come from OUTSIDE this repository

The second mode is for testing a built wheel in a fresh environment,
where importing from the checkout would mean the wheel was never
really under test.

This is not a style preference. An earlier debugging session found that
running these tests inside a live Forge host imported the host's own
installed runtime, because 64 forge.* modules were already in
sys.modules and sys.path never got consulted. Every assertion would
have passed against the wrong code.
"""

import os
import sys


REPO_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


def _import_forge(target):
    """
    Import Forge for the requested mode.

    In checkout mode the repository is put first on sys.path. In
    installed mode it deliberately is not, because prepending it would
    shadow the very package the test run is meant to exercise.
    """
    if target == 'checkout' and REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)

    import forge

    return forge


def forge_under_test():
    """
    Import Forge, verify it came from the intended place, and return it.

    Raises AssertionError with the actual path when the import does not
    match FORGE_TEST_TARGET.
    """
    target = (
        os.environ.get('FORGE_TEST_TARGET')
        or 'checkout'
    ).strip().lower()

    if target not in ('checkout', 'installed'):
        raise AssertionError(
            'FORGE_TEST_TARGET must be "checkout" or "installed", got %r.'
            % target
        )

    forge = _import_forge(target)

    origin = os.path.realpath(
        getattr(forge, '__file__', '') or ''
    )

    repo = os.path.realpath(REPO_ROOT)
    inside_checkout = origin.startswith(repo + os.sep)

    if target == 'checkout' and not inside_checkout:
        raise AssertionError(
            'Expected the checkout Forge at %s but imported %s. '
            'A preloaded or installed Forge is shadowing the source '
            'under test.'
            % (repo, origin or '(unknown)')
        )

    if target == 'installed' and inside_checkout:
        raise AssertionError(
            'Expected an installed Forge but imported %s from the '
            'checkout. The built package was not really under test.'
            % origin
        )

    return forge


def describe_forge_under_test(forge):
    """One line naming exactly what is being tested, for CI logs."""
    return 'FORGE UNDER TEST: %s (mode=%s)' % (
        os.path.realpath(getattr(forge, '__file__', '') or '?'),
        (os.environ.get('FORGE_TEST_TARGET') or 'checkout').lower(),
    )