import sys
import types
import unittest

from forge.adapters.pythonista import pasteboard


class FakeBoard(object):
    """Stands in for UIPasteboard's general pasteboard."""

    def __init__(self, text=''):
        self.text = text

    def string(self):
        return self.text

    def setString_(self, text):
        self.text = text


def fake_clipboard_module():
    module = types.ModuleType('clipboard')
    module.value = 'from the module'
    module.get = lambda: module.value
    module.set = lambda text: setattr(module, 'value', text)
    return module


class PasteboardTests(unittest.TestCase):
    def setUp(self):
        self.saved_board = pasteboard._pasteboard
        self.saved_module = sys.modules.get('clipboard')

    def tearDown(self):
        pasteboard._pasteboard = self.saved_board
        if self.saved_module is None:
            sys.modules.pop('clipboard', None)
        else:
            sys.modules['clipboard'] = self.saved_module

    def test_objc_route_is_used_when_available(self):
        board = FakeBoard()
        pasteboard._pasteboard = lambda: board
        pasteboard.set_text('=== FORGE RUN ===')
        self.assertEqual(board.text, '=== FORGE RUN ===')
        self.assertEqual(pasteboard.get_text(), '=== FORGE RUN ===')

    def test_an_empty_pasteboard_reads_as_empty_text(self):
        pasteboard._pasteboard = lambda: FakeBoard(None)
        self.assertEqual(pasteboard.get_text(), '')

    def test_none_is_written_as_empty_text(self):
        board = FakeBoard('old')
        pasteboard._pasteboard = lambda: board
        pasteboard.set_text(None)
        self.assertEqual(board.text, '')

    def test_falls_back_to_the_clipboard_module_without_objc(self):
        def missing():
            raise ImportError('no objc_util here')
        pasteboard._pasteboard = missing
        module = fake_clipboard_module()
        sys.modules['clipboard'] = module
        self.assertEqual(pasteboard.get_text(), 'from the module')
        pasteboard.set_text('packet')
        self.assertEqual(module.value, 'packet')


if __name__ == '__main__':
    unittest.main()