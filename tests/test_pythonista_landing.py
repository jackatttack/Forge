"""Headless tests for the Pythonista Forge Landing: model, detail HTML, hook rules."""
import os
import tempfile
import unittest

from forge.adapters.pythonista import console_ui
from forge.adapters.pythonista.landing import detail_html
from forge.adapters.pythonista.landing import hook
from forge.adapters.pythonista.landing import live as live_module
from forge.adapters.pythonista.landing import model as landing_model

SOURCE = 'line one\nline two\nline three\nline four\n'


def sample_run(root):
    return {
        'stamp': '20260101_000000', 'mode': 'dev', 'status': 'APPLIED',
        'packet': '=== FORGE RUN ===', 'packet_bytes': 17, 'project_root': root,
        'results': [
            {'op': 'READ', 'status': 'APPLIED', 'target': 'notes.txt',
             'data': {'path': 'notes.txt', 'start': 2, 'end': 3}},
            {'op': 'INSERT', 'status': 'APPLIED', 'target': 'notes.txt',
             'data': {'path': 'notes.txt', 'landed_start': 3, 'landed_end': 3}},
            {'op': 'REPLACE', 'status': 'APPLIED', 'target': 'notes.txt',
             'data': {'path': 'notes.txt'}},
            {'op': 'RUN', 'status': 'SKIPPED_AFTER_FAILURE', 'target': 'tool.py'},
        ],
        'parsed_ops': [
            {'op': 'READ', 'blocks': {}, 'body': '', 'directives': {}},
            {'op': 'INSERT', 'blocks': {}, 'body': 'line three', 'directives': {}},
            {'op': 'REPLACE', 'blocks': {'OLD': 'line 4', 'NEW': 'line four'},
             'body': '', 'directives': {}},
            {'op': 'RUN', 'blocks': {}, 'body': '', 'directives': {}},
        ],
    }


class LandingCase(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        with open(os.path.join(self.root, 'notes.txt'), 'w', encoding='utf-8') as handle:
            handle.write(SOURCE)

    def tearDown(self):
        self.temp.cleanup()

    def model(self, **kwargs):
        return landing_model.LandingModel(sample_run(self.root), **kwargs)


class LandingModelTests(LandingCase):

    def test_locations_come_from_result_data(self):
        read, insert, replace, run_row = self.model().rows
        self.assertEqual((read.path, read.start_line, read.end_line), ('notes.txt', 2, 3))
        self.assertEqual((insert.start_line, insert.end_line), (3, 3))
        self.assertEqual((replace.start_line, replace.end_line), (4, 4))
        self.assertIsNone(run_row.path)

    def test_partial_run_verdict_and_counts(self):
        model = self.model()
        self.assertEqual(model.counts, {'success': 3, 'warning': 1, 'danger': 0})
        self.assertEqual(model.verdict, ('RUN PARTIAL', 'warning'))

    def test_failed_parse_reads_run_status(self):
        model = landing_model.LandingModel({'status': 'FAILED_PARSE', 'results': []})
        self.assertEqual(model.verdict, ('RUN FAILED', 'danger'))

    def test_timings_must_match_results(self):
        run = sample_run(self.root)
        timings = [(result['op'], result['target'], 0.1) for result in run['results']]
        model = landing_model.LandingModel(run, timings=timings, run_elapsed=0.5)
        self.assertTrue(model.has_timings)
        self.assertIn('0.50s total', model.summary_line())
        self.assertFalse(landing_model.LandingModel(run, timings=timings[:2]).has_timings)

    def test_spaced_banner(self):
        self.assertEqual(landing_model.spaced('RUN CLEAN'), 'R U N   C L E A N')


class LandingDetailTests(LandingCase):

    def test_insert_tints_landed_lines(self):
        html = detail_html.change_html(self.model().rows[1], self.root)
        self.assertIn('IN FILE NOW', html)
        self.assertIn('class="code-row hl" id="L3"', html)

    def test_replace_shows_removed_block(self):
        html = detail_html.change_html(self.model().rows[2], self.root)
        self.assertIn('REMOVED', html)
        self.assertIn('<div class="removed">', html)

    def test_op_without_file_has_no_change_view(self):
        self.assertIsNone(detail_html.change_html(self.model().rows[3], self.root))


class LandingHookTests(unittest.TestCase):

    def test_console_output_docks_collapsed(self):
        self.assertTrue(hook.has_console_output(
            {'results': [{'data': {'console': {'text': 'x = 2'}}}]}))
        self.assertFalse(hook.has_console_output({'results': [{'data': {}}]}))
        self.assertFalse(hook.has_console_output(None))

    def test_live_redraw_switch(self):
        self.assertTrue(console_ui.ForgeConsoleUI().live)
        self.assertFalse(console_ui.ForgeConsoleUI(live=False).live)


class LiveRunTests(unittest.TestCase):

    def events(self):
        return [
            {'event': 'run_started', 'stamp': '20260101_000000', 'mode': 'dev'},
            {'event': 'operation_started', 'index': 1, 'op': 'read', 'target': 'a.py', 'total': 2},
            {'event': 'operation_finished', 'op': 'read', 'target': 'a.py',
             'status': 'applied', 'elapsed_seconds': 0.25, 'total': 2},
            {'event': 'operation_started', 'index': 2, 'op': 'run', 'target': 'b.py', 'total': 2},
        ]

    def test_events_build_finished_rows_and_active_op(self):
        live = live_module.LiveRun()
        for event in self.events():
            live.handle(event, now=100.0)
        snapshot = live.snapshot()
        self.assertEqual(snapshot['stamp'], '20260101_000000')
        self.assertEqual(snapshot['total'], 2)
        self.assertEqual(snapshot['finished'],
                         [{'op': 'READ', 'target': 'a.py', 'status': 'APPLIED', 'seconds': 0.25}])
        self.assertEqual(snapshot['active']['op'], 'RUN')
        self.assertEqual(snapshot['active']['started'], 100.0)
        self.assertFalse(snapshot['done'])

    def test_run_finished_clears_active_and_ignores_unknown(self):
        live = live_module.LiveRun()
        for event in self.events():
            live.handle(event)
        version = live.snapshot()['version']
        live.handle({'event': 'something_else'})
        self.assertEqual(live.snapshot()['version'], version)
        live.handle({'event': 'run_finished', 'status': 'applied', 'elapsed_seconds': 1.5})
        snapshot = live.snapshot()
        self.assertTrue(snapshot['done'])
        self.assertIsNone(snapshot['active'])
        self.assertEqual(snapshot['elapsed'], 1.5)

    def test_listener_forwards_records_and_docks_once(self):
        seen, docks = [], []

        class Renderer(object):
            timings = [('READ', 'a.py', 0.25)]

            def __call__(self, event):
                seen.append(event['event'])

            def print_clipboard_status(self, ok):
                return ok

        listener = live_module.LandingListener(Renderer(), dock=docks.append)
        for event in self.events():
            listener(event)
        self.assertEqual(seen, [event['event'] for event in self.events()])
        self.assertEqual(len(docks), 1)
        self.assertIs(docks[0], listener.live)
        self.assertTrue(listener.docked)
        self.assertEqual(listener.timings, [('READ', 'a.py', 0.25)])
        self.assertTrue(listener.print_clipboard_status(True))

    def test_listener_survives_a_failing_dock(self):
        def broken_dock(live):
            raise RuntimeError('no console')

        listener = live_module.LandingListener(None, dock=broken_dock)
        for event in self.events():
            listener(event)
        self.assertFalse(listener.docked)
        self.assertTrue(listener.dock_failed)
        with self.assertRaises(AttributeError):
            listener.timings
