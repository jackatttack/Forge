# -*- coding: utf-8 -*-
"""
RUN OUTPUT: shorten the preview of a successful run, never of a failure.

Result data must always keep the complete streams, whatever OUTPUT says.
"""

import unittest

from forge_case import ForgeCase, bundle


TEN_LINES = 'for n in range(1, 11):\n    print("line %02d" % n)\n'


def run_preview(run, index=0):
    return str((run.get('results') or [])[index].get('preview') or '')


def run_data(run, index=0):
    return (run.get('results') or [])[index].get('data') or {}


class RunOutputMode(ForgeCase):

    def setUp(self):
        super().setUp()
        self.put('ten.py', TEN_LINES)
        self.put('ten_then_fail.py', TEN_LINES + 'raise SystemExit(2)\n')
        self.put(
            'ten_on_stderr.py',
            'import sys\n'
            'for n in range(1, 11):\n'
            '    print("err %02d" % n, file=sys.stderr)\n',
        )

    def run_with(self, script, output=None):
        lines = ['RUN ' + script]
        if output is not None:
            lines.append('OUTPUT: ' + output)
        return self.run_bundle(bundle(*lines))

    def test_default_shows_every_line(self):
        preview = run_preview(self.run_with('ten.py'))
        self.assertIn('line 01', preview)
        self.assertIn('line 10', preview)
        self.assertNotIn('hidden', preview)

    def test_full_matches_the_default(self):
        self.assertEqual(
            run_preview(self.run_with('ten.py', 'full')),
            run_preview(self.run_with('ten.py')),
        )

    def test_tail_n_keeps_the_last_lines_and_counts_the_rest(self):
        preview = run_preview(self.run_with('ten.py', 'tail 3'))
        self.assertNotIn('line 07', preview)
        self.assertIn('line 08', preview)
        self.assertIn('line 10', preview)
        self.assertIn('7 earlier lines hidden', preview)
        self.assertIn('OUTPUT: full', preview)

    def test_tail_without_a_count_uses_the_default(self):
        preview = run_preview(self.run_with('ten.py', 'tail'))
        self.assertNotIn('line 02', preview)
        self.assertIn('line 03', preview)

    def test_summary_keeps_only_the_last_line(self):
        preview = run_preview(self.run_with('ten.py', 'summary'))
        self.assertNotIn('line 09', preview)
        self.assertIn('line 10', preview)

    def test_tail_applies_to_stderr_too(self):
        preview = run_preview(self.run_with('ten_on_stderr.py', 'tail 2'))
        self.assertNotIn('err 08', preview)
        self.assertIn('err 10', preview)

    def test_short_output_is_not_marked_as_hidden(self):
        preview = run_preview(self.run_with('ten.py', 'tail 50'))
        self.assertIn('line 01', preview)
        self.assertNotIn('hidden', preview)

    def test_failed_run_always_shows_full_output(self):
        run = self.run_with('ten_then_fail.py', 'summary')
        self.assertEqual(self.statuses(run), ['FAILED_RUNTIME'])
        preview = run_preview(run)
        self.assertIn('line 01', preview)
        self.assertIn('line 10', preview)
        self.assertNotIn('hidden', preview)

    def test_result_data_keeps_complete_output(self):
        data = run_data(self.run_with('ten.py', 'summary'))
        self.assertIn('line 01', data.get('stdout', ''))
        self.assertEqual(data.get('output'), 'summary')

    def test_invalid_output_value_does_not_run_the_script(self):
        self.put('marker.py', 'open("ran.txt", "w").write("ran")\n')
        for bad_value in ('everything', 'tail 0', 'tail 201', 'tail x', 'summary 3'):
            run = self.run_with('marker.py', bad_value)
            self.assertNotIn('APPLIED', self.statuses(run), bad_value)
            self.assertFalse(self.exists('ran.txt'), bad_value)


if __name__ == '__main__':
    unittest.main()