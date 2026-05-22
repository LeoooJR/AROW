"""
Integration tests for the device selection panel shell.

Block-internal device row behavior lives under ``gui.blocks.device.tests``.
"""

from __future__ import annotations

import pytest

from gui.device import DeviceSelectionPanel

pytestmark = pytest.mark.usefixtures("qapp")


def test_refresh_panel_timer_invokes_batch_refresh(qtbot, monkeypatch) -> None:
    calls: list[int] = []
    real = DeviceSelectionPanel.refresh_last_communication_timestamps

    def tracking(self, *a, **kw):  # type: ignore[no-untyped-def]
        calls.append(1)
        return real(self, *a, **kw)

    monkeypatch.setattr(
        DeviceSelectionPanel,
        "refresh_last_communication_timestamps",
        tracking,
    )
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel._last_communication_refresh_timer.stop()
    panel._last_communication_refresh_timer.setInterval(30)
    panel._last_communication_refresh_timer.start()

    def done() -> bool:
        return len(calls) >= 1

    qtbot.waitUntil(done, timeout=3000)
    assert len(calls) >= 1


def test_device_selection_panel_facade_delegates_placeholder_rows(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)

    panel.add_list_items_placeholder()

    assert panel.available_device_list().count() == 3
    assert panel.current_device() is None
