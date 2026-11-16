# -*- coding: utf-8 -*-
"""
Headless tests for the Pythonista presenter seam.

forge.json may name a presenter module that shows a finished run in place
of the built-in Forge Landing. The seam must never make a run worse: any
missing, broken or unwilling presenter has to end on the built-in landing.
"""

import json
import os
import tempfile
import types
import unittest

from forge.adapters.pythonista import presenter
from forge.core.config import (
    default_config,
    normalise_config,
    resolve_config,
)


FORGE_HOME = os.path.join(os.sep, 'tmp', 'forge-home')


class FakeRenderer(object):
    """Stands in for ForgeConsoleUI: records how it was built."""

    def __init__(self, live=True):
        self.live = live

    def __call__(self, event):
        pass


def fake_module(**members):
    module = types.ModuleType('fake_presenter')
    for name, value in members.items():
        setattr(module, name, value)
    return module


def importer_for(module):
    """An importer that returns module, or fails when module is None."""
    def importer(name):
        if module is None:
            raise ImportError(name)
        return module
    return importer


class Calls(object):
    """A callable that records its calls and returns a fixed answer."""

    def __init__(self, answer=True, error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        return self.answer


class PresenterConfig(unittest.TestCase):

    def test_default_is_no_presenter(self):
        self.assertEqual(default_config()['presenter'], '')

    def test_config_without_presenter_still_normalises(self):
        """Existing configs predate this setting and must keep working."""
        merged = normalise_config({'config_version': 1})
        self.assertEqual(merged['presenter'], '')

    def test_a_dotted_module_name_is_accepted(self):
        merged = normalise_config(
            {'config_version': 1, 'presenter': 'anvil.forge_presenter'})
        self.assertEqual(merged['presenter'], 'anvil.forge_presenter')

    def test_presenter_must_be_a_string(self):
        with self.assertRaises(ValueError):
            normalise_config({'config_version': 1, 'presenter': 42})

    def test_presenter_must_be_a_module_name(self):
        with self.assertRaises(ValueError):
            normalise_config({'config_version': 1, 'presenter': 'not a module'})

    def test_resolved_config_carries_the_stripped_name(self):
        resolved = resolve_config(
            {'config_version': 1, 'presenter': ' anvil.forge_presenter '},
            FORGE_HOME)
        self.assertEqual(resolved['presenter'], 'anvil.forge_presenter')


class PresenterEnvironment(unittest.TestCase):
    """FORGE config reads the presenter name from the environment."""

    def test_environment_carries_the_presenter_name(self):
        from forge.core.environment import make_environment

        environment = make_environment(
            FORGE_HOME, FORGE_HOME, presenter=' anvil.forge_presenter ')
        self.assertEqual(environment['presenter'], 'anvil.forge_presenter')
        self.assertEqual(
            make_environment(FORGE_HOME, FORGE_HOME)['presenter'], '')

    def test_the_name_survives_normalising_an_environment(self):
        from forge.core.environment import (
            make_environment,
            normalise_environment,
        )

        environment = make_environment(
            FORGE_HOME, FORGE_HOME, presenter='anvil.forge_presenter')
        again = normalise_environment(environment)
        self.assertEqual(again['presenter'], 'anvil.forge_presenter')


class ConfiguredName(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, text):
        path = os.path.join(self.home, 'forge.json')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)

    def test_reads_the_name_from_forge_json(self):
        self.write_config(json.dumps(
            {'config_version': 1, 'presenter': 'anvil.forge_presenter'}))
        self.assertEqual(
            presenter.configured_name(self.home), 'anvil.forge_presenter')

    def test_no_config_file_means_no_presenter(self):
        self.assertEqual(presenter.configured_name(self.home), '')

    def test_a_broken_config_means_no_presenter(self):
        self.write_config('{ not json')
        self.assertEqual(presenter.configured_name(self.home), '')


class PresenterCase(unittest.TestCase):

    def tearDown(self):
        presenter._chosen = None
        presenter.last_error = ''


class Load(PresenterCase):

    def test_no_name_loads_nothing(self):
        self.assertIsNone(presenter.load(name=''))

    def test_import_failure_is_recorded_not_raised(self):
        module = presenter.load(name='missing.module',
                                importer=importer_for(None))
        self.assertIsNone(module)
        self.assertIn('could not be imported', presenter.last_error)

    def test_a_module_without_show_after_run_is_refused(self):
        module = presenter.load(name='fake', importer=importer_for(fake_module()))
        self.assertIsNone(module)
        self.assertIn('show_after_run', presenter.last_error)

    def test_a_good_module_is_returned(self):
        good = fake_module(show_after_run=Calls())
        self.assertIs(presenter.load(name='fake', importer=importer_for(good)), good)


class MakeListener(PresenterCase):

    def test_no_presenter_returns_none_for_the_builtin_landing(self):
        self.assertIsNone(presenter.make_listener(FakeRenderer, name=''))

    def test_presenter_without_listener_gets_the_live_console(self):
        good = fake_module(show_after_run=Calls())
        listener = presenter.make_listener(
            FakeRenderer, name='fake', importer=importer_for(good))
        self.assertIsInstance(listener, FakeRenderer)
        self.assertTrue(listener.live)

    def test_presenter_listener_wraps_a_quiet_renderer(self):
        seen = []

        def make_listener(renderer):
            seen.append(renderer)
            return 'the listener'

        good = fake_module(show_after_run=Calls(), make_listener=make_listener)
        listener = presenter.make_listener(
            FakeRenderer, name='fake', importer=importer_for(good))
        self.assertEqual(listener, 'the listener')
        self.assertFalse(seen[0].live)

    def test_a_failing_listener_falls_back_and_unchooses_the_presenter(self):
        shown = Calls()
        bad = fake_module(show_after_run=shown,
                          make_listener=Calls(error=RuntimeError('boom')))
        listener = presenter.make_listener(
            FakeRenderer, name='fake', importer=importer_for(bad))
        self.assertIsNone(listener)
        self.assertIn('make_listener failed', presenter.last_error)

        builtin = Calls()
        presenter.show_after_run({'status': 'APPLIED'}, None, builtin=builtin)
        self.assertEqual(len(shown.calls), 0)
        self.assertEqual(len(builtin.calls), 1)


class ShowAfterRun(PresenterCase):

    def choose(self, show):
        module = fake_module(show_after_run=show)
        presenter.make_listener(
            FakeRenderer, name='fake', importer=importer_for(module))

    def test_a_presenter_that_shows_the_run_wins(self):
        show, builtin = Calls(True), Calls()
        self.choose(show)
        run = {'status': 'APPLIED'}
        self.assertTrue(presenter.show_after_run(run, 'progress', builtin=builtin))
        self.assertEqual(show.calls, [(run, 'progress')])
        self.assertEqual(builtin.calls, [])

    def test_a_presenter_that_declines_hands_over_to_the_builtin(self):
        show, builtin = Calls(False), Calls(True)
        self.choose(show)
        self.assertTrue(presenter.show_after_run({}, None, builtin=builtin))
        self.assertEqual(len(builtin.calls), 1)
        self.assertIn('did not show', presenter.last_error)

    def test_a_presenter_that_raises_hands_over_to_the_builtin(self):
        show, builtin = Calls(error=RuntimeError('boom')), Calls(True)
        self.choose(show)
        self.assertTrue(presenter.show_after_run({}, None, builtin=builtin))
        self.assertEqual(len(builtin.calls), 1)
        self.assertIn('boom', presenter.last_error)

    def test_no_presenter_uses_the_builtin(self):
        builtin = Calls(True)
        self.assertTrue(presenter.show_after_run({}, None, builtin=builtin))
        self.assertEqual(len(builtin.calls), 1)

    def test_the_choice_lasts_one_run(self):
        show, builtin = Calls(True), Calls(True)
        self.choose(show)
        presenter.show_after_run({}, None, builtin=builtin)
        presenter.show_after_run({}, None, builtin=builtin)
        self.assertEqual(len(show.calls), 1)
        self.assertEqual(len(builtin.calls), 1)

    def test_a_failing_builtin_is_swallowed(self):
        builtin = Calls(error=RuntimeError('no console'))
        self.assertFalse(presenter.show_after_run({}, None, builtin=builtin))