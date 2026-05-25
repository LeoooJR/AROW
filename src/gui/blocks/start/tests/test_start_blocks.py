"""Tests for welcome start-screen blocks."""

from __future__ import annotations

import pytest

from gui.blocks.start import StartRecentBlock, WalkthroughBlock
from gui.components import File, WalkthroughButton

pytestmark = pytest.mark.usefixtures("qapp")


def _recent_file_widgets(block: StartRecentBlock) -> list[File]:
    layout = block.recent_files_wrapper.get_layout()
    widgets: list[File] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if isinstance(widget, File):
            widgets.append(widget)
    return widgets


def test_start_recent_block_generates_recent_file_rows(qtbot) -> None:
    block = StartRecentBlock()
    qtbot.addWidget(block)

    rows = _recent_file_widgets(block)

    assert len(rows) == len(block.texts.recent_files)
    assert all(row._file_name_label.text().strip() for row in rows)


def test_start_recent_block_theme_refresh_reaches_file_rows(monkeypatch, qtbot) -> None:
    calls = []

    def spy_apply_theme_icons(self, theme):  # type: ignore[no-untyped-def]
        calls.append((self, theme))

    monkeypatch.setattr(File, "apply_theme_icons", spy_apply_theme_icons)
    block = StartRecentBlock()
    qtbot.addWidget(block)

    block.apply_theme_icons("dark")

    assert len(calls) == len(block.texts.recent_files)
    assert all(theme == "dark" for _, theme in calls)


def test_start_recent_block_oversized_placeholder_count_is_capped(qtbot) -> None:
    block = StartRecentBlock()
    qtbot.addWidget(block)
    before = len(_recent_file_widgets(block))

    block._add_recent_placeholders(count=99)

    added = len(_recent_file_widgets(block)) - before
    assert added == len(block.texts.recent_files)


def test_walkthrough_block_builds_expected_actions(qtbot) -> None:
    block = WalkthroughBlock()
    qtbot.addWidget(block)

    assert block.walkthrough_wifi_button.texts.label == (
        block.texts.walkthrough_wifi_button
    )
    assert block.walkthrough_usb_button.texts.label == (
        block.texts.walkthrough_usb_button
    )


def test_walkthrough_block_theme_refresh_reaches_buttons(monkeypatch, qtbot) -> None:
    calls = []

    def spy_apply_theme_icons(self, theme):  # type: ignore[no-untyped-def]
        calls.append((self, theme))

    monkeypatch.setattr(WalkthroughButton, "apply_theme_icons", spy_apply_theme_icons)
    block = WalkthroughBlock()
    qtbot.addWidget(block)

    block.apply_theme_icons("dark")

    assert calls == [
        (block.walkthrough_wifi_button, "dark"),
        (block.walkthrough_usb_button, "dark"),
    ]
