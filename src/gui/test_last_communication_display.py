"""
Tests for last-communication formatting and live refresh (``gui.device``).

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import datetime as dt

import pytest

from gui.device import (
    DeviceItem,
    DeviceSelectionPanel,
    format_last_communication_short,
)

pytestmark = pytest.mark.usefixtures("qapp")

_NOW = dt.datetime(2026, 5, 7, 12, 0, 0)


@pytest.mark.parametrize(
    ("at,expected_substring"),
    [
        (None, "Never"),
        (_NOW, "Just now"),
        (_NOW - dt.timedelta(seconds=45), "Just now"),
        (_NOW - dt.timedelta(minutes=1), "1 minute ago"),
        (_NOW - dt.timedelta(minutes=2), "2 minutes ago"),
        (_NOW - dt.timedelta(hours=1), "1 hour ago"),
        (_NOW - dt.timedelta(hours=3), "3 hours ago"),
        (_NOW - dt.timedelta(days=1), "1 day ago"),
        (_NOW - dt.timedelta(days=6), "6 days ago"),
    ],
)
def test_format_last_communication_short_relative(
    at: dt.datetime | None, expected_substring: str
) -> None:
    out = format_last_communication_short(at, now=_NOW)
    assert expected_substring in out


def test_format_last_communication_short_absolute_after_one_week() -> None:
    at = _NOW - dt.timedelta(days=10)
    out = format_last_communication_short(at, now=_NOW)
    assert "2026" in out
    assert "Apr" in out or "May" in out


def test_format_future_timestamp_is_just_now() -> None:
    at = _NOW + dt.timedelta(hours=1)
    assert format_last_communication_short(at, now=_NOW) == "Just now"


def test_device_item_static_row_not_refreshed(qtbot) -> None:
    item = DeviceItem(None, text="Phone", last_communication="Active now")
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)
    assert item.ui.time_label.text() == "Active now"
    item.refresh_last_communication_label(now=_NOW)
    assert item.ui.time_label.text() == "Active now"


def test_device_item_live_row_updates_with_now(qtbot) -> None:
    past = _NOW - dt.timedelta(hours=2)
    item = DeviceItem(None, text="Phone", last_communication=past)
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)
    item.refresh_last_communication_label(now=_NOW)
    assert item.ui.time_label.text() == "2 hours ago"
    item.refresh_last_communication_label(now=_NOW + dt.timedelta(hours=2))
    assert item.ui.time_label.text() == "4 hours ago"


def test_device_item_badge_stacks_in_compact_mode_and_restores_when_extended(
    qtbot,
) -> None:
    item = DeviceItem(None, text="Zenfone 11", badge="trusted")
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1

    item.extend_device_item()
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == -1

    item.shorten_device_item()
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1


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
