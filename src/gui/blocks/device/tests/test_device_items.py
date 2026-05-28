"""
Tests for custom device-list rows and the device selection block.

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import datetime as dt

import pytest
from PySide6.QtWidgets import QLabel

from gui.blocks.device import (
    DeviceItem,
    DeviceSelectionBlock,
    format_last_communication_short,
)
from gui.components import StatusBadge
from gui.settings import Settings
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")

_NOW = dt.datetime(2026, 5, 7, 12, 0, 0)


def test_device_item_badge_stays_stacked_in_compact_and_extended_modes(qtbot) -> None:
    item = DeviceItem(None, text="Zenfone 11", badge="trusted")
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)

    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1


@pytest.mark.parametrize(
    ("badge_kind", "text", "property_value"),
    [
        ("active", "Active", "active"),
        ("new", "New", "new"),
    ],
)
def test_device_item_text_badges_use_status_badge(
    qtbot, badge_kind: str, text: str, property_value: str
) -> None:
    item = DeviceItem(None, text="Zenfone 11", badge=badge_kind)
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)

    badges = item.ui.badge_container.findChildren(StatusBadge)

    assert len(badges) == 1
    assert badges[0].objectName() == "device-item-badge"
    assert badges[0].text() == text
    assert badges[0].property("device-item-badge") == property_value
    assert badges[0].property("status-badge") is None


def test_device_item_trusted_badge_keeps_icon_and_uses_status_badge_text(qtbot) -> None:
    item = DeviceItem(None, text="Zenfone 11", badge="trusted")
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)

    badges = item.ui.badge_container.findChildren(StatusBadge)
    plain_labels = [
        label
        for label in item.ui.badge_container.findChildren(QLabel)
        if not isinstance(label, StatusBadge)
    ]

    assert len(badges) == 1
    assert badges[0].objectName() == "device-item-badge"
    assert badges[0].text() == "Trusted"
    assert badges[0].property("device-item-badge") == "trusted-text"
    assert badges[0].property("status-badge") is None
    assert len(plain_labels) == 1
    assert plain_labels[0].pixmap() is not None

    item.extend()
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1

    item.shorten()
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1


def test_device_item_actions_show_only_in_extended_mode(qtbot) -> None:
    item = DeviceItem(None, text="Zenfone 11", last_communication="Active now")
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)

    assert item.ui.time_label.isHidden() is True
    assert item.trash_button.isHidden() is True

    item.extend()
    assert item.ui.time_label.isHidden() is False
    assert item.trash_button.isHidden() is False

    item.shorten()
    assert item.ui.time_label.isHidden() is True
    assert item.trash_button.isHidden() is True


def test_device_item_applies_alert_highlight_on_creation(qtbot) -> None:
    item = DeviceItem(None, text="Unknown Device", alert_highlight=True)
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)

    assert item.alert_highlight is True
    assert item.row_widget.property("alert") is True


def test_device_selection_block_syncs_custom_row_selection(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    first = DeviceItem.add_to_list(block.available_device_list, text="Pixel 9")
    second = DeviceItem.add_to_list(block.available_device_list, text="Zenfone 11")
    qtbot.wait(0)

    block.available_device_list.setCurrentItem(first)
    qtbot.wait(0)
    assert first.row_widget.property("selected") is True
    assert second.row_widget.property("selected") is False

    block.available_device_list.setCurrentItem(second)
    qtbot.wait(0)
    assert first.row_widget.property("selected") is False
    assert second.row_widget.property("selected") is True


def _device_rows(block: DeviceSelectionBlock) -> list[DeviceItem]:
    """Return custom device rows from the block list."""
    return [
        item
        for item in block.available_device_list.iter_items()
        if isinstance(item, DeviceItem)
    ]


def test_device_selection_block_extend_signal_expands_all_rows(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    DeviceItem.add_to_list(
        block.available_device_list,
        text="Pixel 9",
        last_communication="Active now",
    )
    DeviceItem.add_to_list(
        block.available_device_list,
        text="Zenfone 11",
        last_communication="30 min ago",
    )
    qtbot.wait(0)

    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is True
        assert item.trash_button.isHidden() is True

    view_signals.ExtendDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)

    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is False
        assert item.trash_button.isHidden() is False


def test_device_selection_block_shorten_signal_collapses_all_rows(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    DeviceItem.add_to_list(
        block.available_device_list,
        text="Pixel 9",
        last_communication="Active now",
    )
    DeviceItem.add_to_list(
        block.available_device_list,
        text="Zenfone 11",
        last_communication="30 min ago",
    )
    qtbot.wait(0)

    view_signals.ExtendDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)
    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is False

    view_signals.ShortenDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)

    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is True
        assert item.trash_button.isHidden() is True


def test_alert_device_item_can_also_be_selected(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    item = DeviceItem.add_to_list(
        block.available_device_list,
        text="Unknown Device",
        alert_highlight=True,
    )
    qtbot.wait(0)

    block.available_device_list.setCurrentItem(item)
    qtbot.wait(0)
    assert item.row_widget.property("alert") is True
    assert item.row_widget.property("selected") is True


def test_device_item_compact_size_hint_stays_within_viewport(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.resize(340, 520)
    block.show()
    item = DeviceItem.add_to_list(
        block.available_device_list,
        text="Samsung Galaxy S24 Ultra Developer Preview Lab Device With Very Long Friendly Name",
        operating_system="Android 15 Beta 4",
        location="North Charleston, South Carolina",
        badge="trusted",
    )
    qtbot.wait(0)
    item._sync_size_hint()

    viewport_width = block.available_device_list.viewport().width()
    assert viewport_width > 0
    assert item.sizeHint().width() <= viewport_width


def test_device_item_extended_size_hint_stays_within_viewport(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.resize(340, 520)
    block.show()
    item = DeviceItem.add_to_list(
        block.available_device_list,
        text="Samsung Galaxy S24 Ultra Developer Preview Lab Device With Very Long Friendly Name",
        operating_system="Android 15 Beta 4",
        location="North Charleston, South Carolina",
        last_communication="Active now",
        badge="trusted",
    )
    qtbot.wait(0)

    item.extend()
    qtbot.wait(0)
    viewport_width = block.available_device_list.viewport().width()
    assert viewport_width > 0
    assert item.sizeHint().width() <= viewport_width


def test_device_item_compact_text_uses_single_line_elision(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.resize(340, 520)
    block.show()
    full_name = "Unknown Device With A Very Long Friendly Name"
    item = DeviceItem.add_to_list(
        block.available_device_list,
        text=full_name,
        operating_system="Android 15",
        location="South Adrianstad, GA",
        badge="new",
    )
    qtbot.wait(0)
    item._sync_size_hint()

    assert item.name == full_name
    assert "\n" not in item.ui.name_label.text()
    assert "\n" not in item.ui.subtitle_label.text()
    assert item.ui.name_label.wordWrap() is False
    assert item.ui.subtitle_label.wordWrap() is False


def test_device_item_extended_text_uses_single_line_elision(qtbot) -> None:
    item = DeviceItem(
        None,
        text="Unknown Device With A Very Long Friendly Name",
        operating_system="Android 15",
        location="South Adrianstad, GA",
        badge="new",
    )
    qtbot.addWidget(item.row_widget)
    item.extend()

    assert item.name == "Unknown Device With A Very Long Friendly Name"
    assert "\n" not in item.ui.name_label.text()
    assert "\n" not in item.ui.subtitle_label.text()
    assert item.ui.name_label.wordWrap() is False
    assert item.ui.subtitle_label.wordWrap() is False


def test_device_selection_block_highlight_attention_pulses_list(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    assert block.available_device_list.objectName() == "available-device-list"

    view_signals.MapTabActivated.emit()
    qtbot.wait(80)

    level = block.available_device_list.property("device-list-highlight-level")
    assert level is not None
    assert level != "0"

    qtbot.wait(Settings.ANIMATION.ATTENTION_HIGHLIGHT_DURATION + 100)

    assert block.available_device_list.property("device-list-highlight-level") == "0"


def test_device_selection_block_map_tab_skips_highlight_when_device_selected(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    item = DeviceItem.add_to_list(
        block.available_device_list,
        id="device-1",
        text="Phone",
        type="available",
        badge="new",
        operating_system="Android",
        location="N/A",
        last_communication="Active now",
    )
    block.available_device_list.setCurrentItem(item)
    view_signals.DeviceSelectionSucceeded.emit({"id": "device-1", "name": "Phone"})
    qtbot.wait(0)

    view_signals.MapTabActivated.emit()
    qtbot.wait(80)

    assert block.available_device_list.property("device-list-highlight-level") in (
        None,
        "0",
        0,
    )


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
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)
    assert item.ui.time_label.text() == "Active now"
    item.refresh_last_communication_label(now=_NOW)
    assert item.ui.time_label.text() == "Active now"


def test_device_item_live_row_updates_with_now(qtbot) -> None:
    past = _NOW - dt.timedelta(hours=2)
    item = DeviceItem(None, text="Phone", last_communication=past)
    qtbot.addWidget(item.row_widget)
    qtbot.wait(0)
    item.refresh_last_communication_label(now=_NOW)
    assert item.ui.time_label.text() == "2 hours ago"
    item.refresh_last_communication_label(now=_NOW + dt.timedelta(hours=2))
    assert item.ui.time_label.text() == "4 hours ago"


def test_device_selection_block_seeds_placeholders_from_debug_signal(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)

    assert block.available_device_list.count() == 0

    view_signals.UiConstraintsDisabled.emit()
    qtbot.wait(0)

    assert block.available_device_list.count() == 3


def test_device_selection_block_ignores_missing_remove_request(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    DeviceItem.add_to_list(block.available_device_list, id="known", text="Pixel 9")
    qtbot.wait(0)

    view_signals.RemoveDeviceRequested.emit("missing")
    qtbot.wait(0)

    assert block.available_device_list.count() == 1


def test_device_selection_block_handles_failed_selection_without_current_item(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    DeviceItem.add_to_list(block.available_device_list, id="known", text="Pixel 9")
    block.available_device_list.setCurrentItem(None)

    view_signals.DeviceSelectionFailed.emit({"id": "missing", "name": "Missing"})
    qtbot.wait(0)

    assert block.available_device_list.currentItem() is None
