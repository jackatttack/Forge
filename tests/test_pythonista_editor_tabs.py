# -*- coding: utf-8 -*-
"""Headless tests: open Pythonista editor tabs follow Forge's writes."""

import os
import tempfile
import unittest

from forge.adapters.pythonista import editor_tabs
from forge.core import host_hooks
from forge.core.file_safety import write_text


class FakeTab(object):
    """Stands in for a loaded editor tab; positions count UTF-16 units."""

    def __init__(self, path, text):
        self.path = os.path.realpath(path)
        self.buffer = text

    def text(self):
        return self.buffer

    def replace(self, start, end, new_text):
        units = self.buffer.encode('utf-16-le')
        self.buffer = (
            units[:start * 2] + new_text.encode('utf-16-le') + units[end * 2:]
        ).decode('utf-16-le')


class BrokenTab(FakeTab):
    def text(self):
        raise RuntimeError('editor went away')


def use_tabs(tabs):
    host_hooks.clear()
    editor_tabs.tab_source = lambda: tabs
    editor_tabs.register_with_forge()


def reset():
    host_hooks.clear()
    editor_tabs.tab_source = editor_tabs.pythonista_tabs


def scratch_file(text):
    folder = tempfile.mkdtemp(prefix='forge-tabs-')
    path = os.path.join(folder, 'target.py')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path


def read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def test_no_hooks_writes_as_before():
    host_hooks.clear()
    path = scratch_file('VALUE = 1')
    write_text(path, 'VALUE = 2')
    assert read(path) == 'VALUE = 2'


def test_open_tab_follows_write_across_emoji():
    path = scratch_file('# 👋 one\nVALUE = 1')
    tab = FakeTab(path, '# 👋 one\nVALUE = 1\n')  # the editor's extra newline
    try:
        use_tabs([tab])
        write_text(path, '# 👋 one\nVALUE = 2')
        assert read(path) == '# 👋 one\nVALUE = 2'
        assert tab.buffer == '# 👋 one\nVALUE = 2', repr(tab.buffer)
    finally:
        reset()


def test_differing_tab_refuses_and_disk_is_untouched():
    path = scratch_file('VALUE = 1')
    tab = FakeTab(path, 'VALUE = 99')  # unsaved edit, or a stale copy
    try:
        use_tabs([tab])
        try:
            write_text(path, 'VALUE = 2')
        except host_hooks.HostRefusal as refusal:
            assert 'open in a Pythonista editor tab' in str(refusal)
        else:
            raise AssertionError('write should have been refused')
        assert read(path) == 'VALUE = 1'
        assert tab.buffer == 'VALUE = 99'
    finally:
        reset()


def test_tabs_for_other_files_are_left_alone():
    path = scratch_file('VALUE = 1')
    other = FakeTab(scratch_file('OTHER = 1'), 'OTHER = 1')
    try:
        use_tabs([other])
        write_text(path, 'VALUE = 2')
        assert other.buffer == 'OTHER = 1'
    finally:
        reset()


def test_broken_tab_never_blocks_a_write():
    path = scratch_file('VALUE = 1')
    try:
        use_tabs([BrokenTab(path, '')])
        write_text(path, 'VALUE = 2')
        assert read(path) == 'VALUE = 2'
    finally:
        reset()


def test_changed_span_is_the_smallest_middle():
    assert editor_tabs.changed_span('VALUE = 1\n', 'VALUE = 2') == (8, 10, 9)
    assert editor_tabs.changed_span('abc', 'abc') == (3, 3, 3)
    assert editor_tabs.changed_span('aXc', 'aYYc') == (1, 2, 3)
    assert editor_tabs.changed_span('', 'new') == (0, 0, 3)


class EditorTabsTests(unittest.TestCase):
    """unittest discovery only collects TestCase classes."""

    def test_no_hooks_writes_as_before(self):
        test_no_hooks_writes_as_before()

    def test_open_tab_follows_write_across_emoji(self):
        test_open_tab_follows_write_across_emoji()

    def test_differing_tab_refuses_and_disk_is_untouched(self):
        test_differing_tab_refuses_and_disk_is_untouched()

    def test_tabs_for_other_files_are_left_alone(self):
        test_tabs_for_other_files_are_left_alone()

    def test_broken_tab_never_blocks_a_write(self):
        test_broken_tab_never_blocks_a_write()

    def test_changed_span_is_the_smallest_middle(self):
        test_changed_span_is_the_smallest_middle()


def main():
    test_no_hooks_writes_as_before()
    test_open_tab_follows_write_across_emoji()
    test_differing_tab_refuses_and_disk_is_untouched()
    test_tabs_for_other_files_are_left_alone()
    test_broken_tab_never_blocks_a_write()
    test_changed_span_is_the_smallest_middle()
    print('PYTHONISTA EDITOR TABS PASS')


if __name__ == '__main__':
    main()
