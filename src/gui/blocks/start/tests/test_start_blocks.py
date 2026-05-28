"""Tests for welcome start-screen blocks."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from gui.blocks.start import (
    ConnectionActionsBlock,
    OperatorReadinessBlock,
    StartRecentBlock,
    WalkthroughBlock,
)
from gui.components import File, StatusBadge, WalkthroughButton
from gui.signals import view_signals

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
    assert all(row._file_date_label is not None for row in rows)


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


def test_operator_readiness_block_builds_expected_rows(qtbot) -> None:
    block = OperatorReadinessBlock()
    qtbot.addWidget(block)

    assert block.ui.title.text() == block.texts.title
    assert len(block.ui.rows) == len(block.texts.default_rows)
    assert block.ui.rows[0].ui.label.text() == "Host"
    assert isinstance(block.ui.rows[0].ui.status, StatusBadge)
    assert block.ui.rows[0].ui.status.text() == "PENDING"
    assert block.ui.rows[0].ui.status.kind() == "ready"
    assert block.ui.rows[0].ui.status.property("readiness-status-chip") == "ready"

    block.ui.rows[0].update("Host", "ADB bridge stopped", "ERROR", "error")

    assert block.ui.rows[0].ui.status.text() == "ERROR"
    assert block.ui.rows[0].ui.status.kind() == "error"
    assert block.ui.rows[0].ui.status.property("readiness-status-chip") == "error"


def test_connection_actions_block_builds_unwired_buttons(qtbot) -> None:
    block = ConnectionActionsBlock()
    qtbot.addWidget(block)
    add_device_spy = QSignalSpy(view_signals.AddDeviceRequested)

    qtbot.mouseClick(block.wifi_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(block.usb_button, Qt.MouseButton.LeftButton)

    assert isinstance(block.wifi_button, WalkthroughButton)
    assert isinstance(block.usb_button, WalkthroughButton)
    assert block.wifi_button.texts.label == block.texts.wifi_button
    assert block.usb_button.texts.label == block.texts.usb_button
    assert add_device_spy.count() == 0


def test_connection_actions_block_centers_button_group(qtbot) -> None:
    block = ConnectionActionsBlock()
    qtbot.addWidget(block)

    body_layout = block.ui.body_wrapper.get_layout()

    assert body_layout.count() == 3
    assert body_layout.itemAt(0).spacerItem() is not None
    assert body_layout.itemAt(1).widget() is block.ui.buttons_wrapper
    assert body_layout.itemAt(2).spacerItem() is not None


def test_connection_actions_block_theme_refresh_reaches_buttons(
    monkeypatch, qtbot
) -> None:
    calls = []

    def spy_apply_theme_icons(self, theme):  # type: ignore[no-untyped-def]
        calls.append((self, theme))

    monkeypatch.setattr(WalkthroughButton, "apply_theme_icons", spy_apply_theme_icons)
    block = ConnectionActionsBlock()
    qtbot.addWidget(block)

    block.apply_theme_icons("dark")

    assert calls == [
        (block.wifi_button, "dark"),
        (block.usb_button, "dark"),
    ]
