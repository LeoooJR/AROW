"""Tests for shared collapsible side-panel behavior."""

from __future__ import annotations

import pytest

from gui.blocks.activity import ActivityLogBlock
from gui.blocks.card import BridgeStatusCardBlock, IdentityCardBlock
from gui.blocks.device import DeviceSelectionBlock
from gui.device import DeviceSelectionPanel
from gui.host import HostPanel
from gui.location import LocationPanel
from gui.logs import LogPanel
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.parametrize(
    ("panel_cls", "signal_name"),
    [
        (DeviceSelectionPanel, "DeviceSelectionPanelVisibilityRequested"),
        (HostPanel, "HostPanelVisibilityRequested"),
        (LogPanel, "LogPanelVisibilityRequested"),
        (LocationPanel, "LocationPanelVisibilityRequested"),
    ],
)
def test_collapsible_panel_button_toggles_and_emits_signal(
    qtbot, panel_cls, signal_name
) -> None:
    panel = panel_cls()
    qtbot.addWidget(panel)
    signal = getattr(view_signals, signal_name)

    assert panel.is_panel_visible() is True

    with qtbot.waitSignal(signal) as emitted:
        panel.ui.expand_button.click()

    assert emitted.args == [False]
    assert panel.is_panel_visible() is False


@pytest.mark.parametrize(
    "panel_cls",
    [DeviceSelectionPanel, HostPanel, LogPanel, LocationPanel],
)
def test_collapsible_panel_show_and_hide_methods_sync_toggle_state(
    qtbot, panel_cls
) -> None:
    panel = panel_cls()
    qtbot.addWidget(panel)

    panel.hide_panel()

    assert panel.is_panel_visible() is False
    assert panel.ui.expand_button._icon == panel._panel_config.collapsed_icon

    panel.show_panel()

    assert panel.is_panel_visible() is True
    assert panel.ui.expand_button._icon == panel._panel_config.expanded_icon


def test_concrete_panels_keep_expected_body_widgets(qtbot) -> None:
    device_panel = DeviceSelectionPanel()
    host_panel = HostPanel()
    log_panel = LogPanel()
    location_panel = LocationPanel()
    for panel in (device_panel, host_panel, log_panel, location_panel):
        qtbot.addWidget(panel)

    assert isinstance(device_panel.ui.device_selection_block, DeviceSelectionBlock)
    assert isinstance(host_panel.ui.identity_card, IdentityCardBlock)
    assert isinstance(host_panel.ui.bridge_card, BridgeStatusCardBlock)
    assert isinstance(log_panel.ui.activity_log_block, ActivityLogBlock)
    assert log_panel.logs_list() is log_panel.ui.activity_log_block.logs_list
    assert (
        log_panel.file_display_widget()
        is log_panel.ui.activity_log_block.file_display_widget
    )
    assert location_panel.ui.railway_input.placeholderText() == (
        location_panel.texts.railway_input
    )
    assert location_panel.ui.kilometric_input.placeholderText() == (
        location_panel.texts.kilometric_input
    )


def test_host_panel_extend_and_shorten_control_bridge_card(qtbot) -> None:
    panel = HostPanel()
    qtbot.addWidget(panel)

    assert panel.ui.bridge_card.isHidden() is True

    panel.extend_panel()

    assert panel.ui.bridge_card.isHidden() is False

    panel.shorten_panel()

    assert panel.ui.bridge_card.isHidden() is True


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
    panel.hide_panel()

    assert calls == [False, True]
