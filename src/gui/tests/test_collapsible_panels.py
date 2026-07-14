"""Tests for shared side-panel shell behavior."""

from __future__ import annotations

import pytest

from gui.blocks.activity import ActivityLogBlock
from gui.blocks.device import DeviceSelectionBlock
from gui.device_panel import DeviceSelectionPanel
from gui.log_panel import LogPanel

pytestmark = pytest.mark.usefixtures("qapp")


def test_concrete_panels_keep_expected_body_widgets(qtbot) -> None:
    device_panel = DeviceSelectionPanel()
    log_panel = LogPanel()
    for panel in (device_panel, log_panel):
        qtbot.addWidget(panel)

    assert isinstance(device_panel.ui.device_selection_block, DeviceSelectionBlock)
    assert isinstance(log_panel.ui.activity_log_block, ActivityLogBlock)
    assert log_panel.logs_list() is log_panel.ui.activity_log_block.logs_list
    assert (
        log_panel.file_display_widget()
        is log_panel.ui.activity_log_block.file_display_widget
    )


def test_log_panel_refresh_layout_delegates_to_activity_block(
    qtbot, monkeypatch
) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    calls: list[bool] = []

    def refresh_spy(*, deferred: bool = True) -> None:
        calls.append(deferred)

    monkeypatch.setattr(panel.ui.activity_log_block, "refresh_layout", refresh_spy)

    panel.refresh_layout(deferred=False)
    panel.refresh_layout(deferred=True)

    assert calls == [False, True]
