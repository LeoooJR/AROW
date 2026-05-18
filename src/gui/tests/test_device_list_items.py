"""
Tests for custom device-list row layout, selection, and compact/extended display.

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import pytest

from gui.device import DeviceItem, DeviceSelectionPanel

pytestmark = pytest.mark.usefixtures("qapp")


def test_device_item_badge_stays_stacked_in_compact_and_extended_modes(
    qtbot,
) -> None:
    item = DeviceItem(None, text="Zenfone 11", badge="trusted")
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1

    item.extend_device_item()
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1

    item.shorten_device_item()
    assert item.ui.center.get_layout().indexOf(item.ui.badge_container) == 1
    assert item.ui.title_row.get_layout().indexOf(item.ui.badge_container) == -1


def test_device_item_actions_show_only_in_extended_mode(qtbot) -> None:
    item = DeviceItem(None, text="Zenfone 11", last_communication="Active now")
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    assert item.ui.time_label.isHidden() is True
    assert item.ui.trash_button.isHidden() is True

    item.extend_device_item()
    assert item.ui.time_label.isHidden() is False
    assert item.ui.trash_button.isHidden() is False

    item.shorten_device_item()
    assert item.ui.time_label.isHidden() is True
    assert item.ui.trash_button.isHidden() is True


def test_device_item_applies_alert_highlight_on_creation(qtbot) -> None:
    item = DeviceItem(None, text="Unknown Device", alert_highlight=True)
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    assert item.alert_highlight is True
    assert item.ui.row.property("alert") is True


def test_device_selection_panel_syncs_custom_row_selection(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel.show()
    first = DeviceItem.add_to_list(panel.ui.available_device_list, text="Pixel 9")
    second = DeviceItem.add_to_list(panel.ui.available_device_list, text="Zenfone 11")
    qtbot.wait(0)

    panel.ui.available_device_list.setCurrentItem(first)
    qtbot.wait(0)
    assert first.ui.row.property("selected") is True
    assert second.ui.row.property("selected") is False

    panel.ui.available_device_list.setCurrentItem(second)
    qtbot.wait(0)
    assert first.ui.row.property("selected") is False
    assert second.ui.row.property("selected") is True


def test_alert_device_item_can_also_be_selected(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel.show()
    item = DeviceItem.add_to_list(
        panel.ui.available_device_list,
        text="Unknown Device",
        alert_highlight=True,
    )
    qtbot.wait(0)

    panel.ui.available_device_list.setCurrentItem(item)
    qtbot.wait(0)
    assert item.ui.row.property("alert") is True
    assert item.ui.row.property("selected") is True


def test_device_item_compact_size_hint_stays_within_viewport(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel.resize(340, 520)
    panel.show()
    item = DeviceItem.add_to_list(
        panel.ui.available_device_list,
        text="Samsung Galaxy S24 Ultra Developer Preview Lab Device With Very Long Friendly Name",
        operating_system="Android 15 Beta 4",
        location="North Charleston, South Carolina",
        badge="trusted",
    )
    qtbot.wait(0)
    item._sync_size_hint()

    viewport_width = panel.ui.available_device_list.viewport().width()
    assert viewport_width > 0
    assert item.sizeHint().width() <= viewport_width


def test_device_item_extended_size_hint_stays_within_viewport(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel.resize(340, 520)
    panel.show()
    item = DeviceItem.add_to_list(
        panel.ui.available_device_list,
        text="Samsung Galaxy S24 Ultra Developer Preview Lab Device With Very Long Friendly Name",
        operating_system="Android 15 Beta 4",
        location="North Charleston, South Carolina",
        last_communication="Active now",
        badge="trusted",
    )
    qtbot.wait(0)

    item.extend_device_item()
    qtbot.wait(0)
    viewport_width = panel.ui.available_device_list.viewport().width()
    assert viewport_width > 0
    assert item.sizeHint().width() <= viewport_width


def test_device_item_compact_text_uses_single_line_elision(qtbot) -> None:
    panel = DeviceSelectionPanel()
    qtbot.addWidget(panel)
    panel.resize(340, 520)
    panel.show()
    full_name = "Unknown Device With A Very Long Friendly Name"
    item = DeviceItem.add_to_list(
        panel.ui.available_device_list,
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
    qtbot.addWidget(item.ui.row)
    item.extend_device_item()

    assert item.name == "Unknown Device With A Very Long Friendly Name"
    assert "\n" not in item.ui.name_label.text()
    assert "\n" not in item.ui.subtitle_label.text()
    assert item.ui.name_label.wordWrap() is False
    assert item.ui.subtitle_label.wordWrap() is False
