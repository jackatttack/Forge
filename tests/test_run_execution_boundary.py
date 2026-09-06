# -*- coding: utf-8 -*-
"""Focused RUN boundary tests, runnable directly inside Pythonista Forge.

Load the checkout operation under a private name. Its safe_target dependency
comes from the already selected Forge package; this tests the changed operation,
not isolation or integration of the entire checkout.
"""
import importlib.util
import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPERATION_PATH = os.path.join(
    ROOT, 'forge', 'packages', 'core_ops', 'run', 'op.py'
)


class RunExecutionBoundaryTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            'forge_run_boundary_under_test', OPERATION_PATH
        )
        self.operation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.operation)

    def run_source(self, source):
        """Exercise RUN under a host exit hook and verify host restoration."""
        saved_exit = sys.exit
        saved_main = sys.modules.get('__main__')
        saved_argv = list(sys.argv)
        saved_path = list(sys.path)
        saved_cwd = os.getcwd()
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        host_exit_calls = []

        def host_exit(code=0):
            host_exit_calls.append(code)
            raise KeyboardInterrupt('Host exit hook called')

        try:
            with tempfile.TemporaryDirectory() as project_root:
                script_path = os.path.join(project_root, 'child.py')
                with open(script_path, 'w', encoding='utf-8') as handle:
                    handle.write(source)

                result = {}
                sys.exit = host_exit
                try:
                    self.operation.execute(
                        {'project_root': project_root},
                        {'target': 'child.py', 'directives': {}},
                        result,
                    )
                except BaseException as error:
                    self.fail(
                        'RUN allowed {} to escape'.format(type(error).__name__)
                    )

                self.assertIs(sys.exit, host_exit)
                self.assertIs(sys.modules.get('__main__'), saved_main)
                self.assertEqual(sys.argv, saved_argv)
                self.assertEqual(sys.path, saved_path)
                self.assertEqual(os.getcwd(), saved_cwd)
                self.assertIs(sys.stdout, saved_stdout)
                self.assertIs(sys.stderr, saved_stderr)
                self.assertEqual(host_exit_calls, [])
                return result
        finally:
            sys.exit = saved_exit

    def test_exit_and_exception_reporting(self):
        cases = [
            ('normal', 'print("normal completion")\n', 0, ''),
            ('exit default', 'import sys\nsys.exit()\n', 0, ''),
            ('exit zero', 'import sys\nsys.exit(0)\n', 0, ''),
            ('exit seven', 'import sys\nsys.exit(7)\n', 7, ''),
            ('exit text', 'import sys\nsys.exit("reason")\n', 1, 'reason'),
            ('direct exit', 'raise SystemExit(3)\n', 3, ''),
            ('exception', 'raise ValueError("broken")\n', 1, 'ValueError'),
            ('interrupt', 'raise KeyboardInterrupt()\n', 130, 'KeyboardInterrupt'),
            ('generator exit', 'raise GeneratorExit()\n', 1, 'GeneratorExit'),
            ('syntax', 'if :\n', 1, 'SyntaxError'),
        ]
        for label, source, code, diagnostic in cases:
            with self.subTest(case=label):
                result = self.run_source(source)
                self.assertEqual(result['data']['exit_code'], code)
                self.assertIs(type(result['data']['exit_code']), int)
                expected = 'APPLIED' if code == 0 else 'FAILED_RUNTIME'
                self.assertEqual(result['status'], expected)
                if diagnostic:
                    self.assertIn(diagnostic, result['data']['stderr'])

    def test_script_is_registered_main(self):
        result = self.run_source(
            'import __main__\n'
            'import sys\n'
            'assert __main__.__dict__ is globals()\n'
            'assert __main__.__file__ == __file__\n'
            'assert sys.argv[0] == __file__\n'
            'print("MAIN IDENTITY PASS")\n'
        )
        self.assertEqual(result['status'], 'APPLIED')
        self.assertIn('MAIN IDENTITY PASS', result['data']['stdout'])

    def test_default_unittest_discovery_and_exit(self):
        for should_pass in (True, False):
            with self.subTest(should_pass=should_pass):
                source = (
                    'import unittest\n'
                    'class ChildTest(unittest.TestCase):\n'
                    '    def test_marker(self):\n'
                    '        print("CHILD TEST EXECUTED")\n'
                    '        self.assertTrue({!r})\n'
                    'if __name__ == "__main__":\n'
                    '    unittest.main()\n'
                ).format(should_pass)
                result = self.run_source(source)
                self.assertEqual(
                    result['data']['exit_code'], 0 if should_pass else 1
                )
                self.assertIs(type(result['data']['exit_code']), int)
                self.assertIn('Ran 1 test', result['data']['stderr'])
                self.assertIn('CHILD TEST EXECUTED', result['data']['stdout'])
                self.assertEqual(
                    result['status'],
                    'APPLIED' if should_pass else 'FAILED_RUNTIME',
                )


def main():
    suite = unittest.TestLoader().loadTestsFromTestCase(
        RunExecutionBoundaryTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError('RUN execution boundary regression failed')
    print('RUN EXECUTION BOUNDARY PASS')


if __name__ == '__main__':
    main()