"""Tests for device selection block behavior and signal wiring."""

from __future__ import annotations

import datetime as dt

import pytest

from gui.blocks.device import DeviceItem, DeviceSelectionBlock
from gui.signals import signals

pytestmark = pytest.mark.usefixtures("qapp")

_NOW = dt.datetime(2026, 5, 7, 12, 0, 0)


def _device_rows(block: DeviceSelectionBlock) -> list[DeviceItem]:
    """Return custom device rows from the block list."""
    return [
        item
        for item in block.available_device_list.iter_items()
        if isinstance(item, DeviceItem)
    ]


def _device_payload(device_id: str, name: str, minutes_ago: int = 0) -> dict:
    """Build a test device payload."""
    return {
        "id": device_id,
        "name": name,
        "os": "15",
        "last_communication": _NOW - dt.timedelta(minutes=minutes_ago),
    }


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


def test_device_selection_block_hides_empty_state_when_devices_exist(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    DeviceItem.add_to_list(block.available_device_list, text="Pixel 9")
    qtbot.wait(0)

    assert block.ui.available_device_empty_state.isHidden() is True
    assert block.ui.select_helper_text.isVisible() is True
    assert block.ui.buttons_wrapper.isVisible() is True


def test_device_selection_block_empty_state_buttons_emit_actions(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()
    qtbot.wait(0)

    with qtbot.waitSignal(signals.DEVICE.AddDeviceRequested):
        block.ui.available_device_empty_state.ui.add_button.click()

    with qtbot.waitSignal(signals.DEVICE.RefreshDeviceListRequested):
        block.ui.available_device_empty_state.ui.refresh_button.click()


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

    signals.UI.ExtendDeviceSelectionPanelRequested.emit()
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

    signals.UI.ExtendDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)
    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is False

    signals.UI.ShortenDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)

    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is True
        assert item.trash_button.isHidden() is True


def test_device_selection_block_extends_new_authenticated_device(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    signals.UI.ExtendDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)
    block._on_authentification_succeeded(
        {
            "id": "new-phone",
            "name": "Pixel 9",
            "os": "15",
            "last_communication": _NOW,
        }
    )
    qtbot.wait(0)

    item = _device_rows(block)[0]
    assert item.ui.time_label.isHidden() is False
    assert item.trash_button.isHidden() is False


def test_device_selection_block_extends_refreshed_devices(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    signals.UI.ExtendDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)
    block._on_devices_updated(
        [
            _device_payload("first-phone", "Pixel 9"),
            _device_payload("second-phone", "Zenfone 11", minutes_ago=30),
        ]
    )
    qtbot.wait(0)

    for item in _device_rows(block):
        assert item.ui.time_label.isHidden() is False
        assert item.trash_button.isHidden() is False


def test_device_selection_block_keeps_new_rows_shortened_after_shorten(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    signals.UI.ExtendDeviceSelectionPanelRequested.emit()
    signals.UI.ShortenDeviceSelectionPanelRequested.emit()
    qtbot.wait(0)
    block._on_devices_updated([_device_payload("first-phone", "Pixel 9")])
    qtbot.wait(0)

    item = _device_rows(block)[0]
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


def test_device_selection_block_highlight_attention_pulses_list(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block.show()

    signals.UI.MapTabActivated.emit()
    qtbot.wait(80)

    assert block.available_device_list.property("device-list-highlight-level") != "0"


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
    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Phone")
    qtbot.wait(0)

    signals.UI.MapTabActivated.emit()
    qtbot.wait(80)

    assert block.available_device_list.property("device-list-highlight-level") in (
        None,
        "0",
        0,
    )


def test_device_selection_block_ignores_missing_remove_request(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    DeviceItem.add_to_list(block.available_device_list, id="known", text="Pixel 9")
    qtbot.wait(0)

    signals.DEVICE.RemoveDeviceRequested.emit("missing")
    qtbot.wait(0)

    assert block.available_device_list.count() == 1


def test_device_selection_block_handles_failed_selection_without_current_item(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    DeviceItem.add_to_list(block.available_device_list, id="known", text="Pixel 9")
    block.available_device_list.setCurrentItem(None)

    signals.DEVICE.DeviceSelectionFailed.emit("missing", "Missing")
    qtbot.wait(0)

    assert block.available_device_list.currentItem() is None


def test_device_selection_block_timer_tick_refreshes_badges(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    at = _NOW - dt.timedelta(minutes=5)
    item = DeviceItem.add_to_list(
        block.available_device_list,
        text="Phone",
        badge="new",
        last_communication=at,
    )
    qtbot.wait(0)

    block._on_refresh_timer_tick(now=_NOW)

    assert item.badge == "trusted"


def test_device_selection_block_initial_current_row_still_emits_selection_request(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    item = DeviceItem.add_to_list(
        block.available_device_list, id="device-1", text="Pixel 9"
    )
    block.available_device_list.setCurrentItem(item)

    with qtbot.waitSignal(signals.DEVICE.DeviceSelectionRequested) as blocker:
        block._on_device_selected(item)

    assert blocker.args == ["device-1", "Pixel 9"]


def test_device_selection_block_ignores_click_on_active_device(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    item = DeviceItem.add_to_list(
        block.available_device_list, id="device-1", text="Pixel 9"
    )
    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Pixel 9")
    qtbot.wait(0)

    with qtbot.waitSignal(
        signals.DEVICE.DeviceSelectionRequested, timeout=100, raising=False
    ) as blocker:
        block._on_device_selected(item)
        qtbot.wait(120)

    assert blocker.signal_triggered is False


def test_device_selection_block_marks_matching_device_active_by_id(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    first = DeviceItem.add_to_list(
        block.available_device_list, id="device-1", text="Pixel 9"
    )
    second = DeviceItem.add_to_list(
        block.available_device_list, id="device-2", text="Zenfone 11"
    )
    block.available_device_list.setCurrentItem(second)

    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Pixel 9")
    qtbot.wait(0)

    assert first.badge == "active"
    assert second.badge != "active"
    assert block.available_device_list.currentItem() is first


def test_device_selection_block_preserves_active_device_on_refresh(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block._on_devices_updated(
        [
            _device_payload("device-1", "Pixel 9"),
            _device_payload("device-2", "Zenfone 11", minutes_ago=30),
        ]
    )
    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Pixel 9")
    qtbot.wait(0)

    block._on_devices_updated(
        [
            _device_payload("device-1", "Pixel 9"),
            _device_payload("device-2", "Zenfone 11", minutes_ago=10),
        ]
    )
    qtbot.wait(0)

    active_item = block.available_device_list.currentItem()

    assert block._active_device_id == "device-1"
    assert active_item is not None
    assert isinstance(active_item, DeviceItem)
    assert active_item.id == "device-1"
    assert active_item.badge == "active"


def test_device_selection_block_preserves_active_device_after_adb_id_rebind(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block._on_devices_updated(
        [
            _device_payload("192.168.0.10:5555", "Pixel 9"),
            _device_payload("device-2", "Zenfone 11", minutes_ago=30),
        ]
    )
    signals.DEVICE.DeviceSelectionSucceeded.emit(
        "sim-1", "192.168.0.10:5555", "Pixel 9"
    )
    qtbot.wait(0)

    block._on_devices_updated(
        [
            _device_payload("192.168.0.10:37849", "Pixel 9"),
            _device_payload("device-2", "Zenfone 11", minutes_ago=10),
        ],
        {"192.168.0.10:5555": "192.168.0.10:37849"},
    )
    qtbot.wait(0)

    active_item = block.available_device_list.currentItem()

    assert block._active_device_id == "192.168.0.10:37849"
    assert active_item is not None
    assert isinstance(active_item, DeviceItem)
    assert active_item.id == "192.168.0.10:37849"
    assert active_item.badge == "active"


def test_device_selection_block_clears_active_device_when_refresh_drops_it(
    qtbot,
) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    block._on_devices_updated(
        [
            _device_payload("device-1", "Pixel 9"),
            _device_payload("device-2", "Zenfone 11", minutes_ago=30),
        ]
    )
    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Pixel 9")
    qtbot.wait(0)

    block._on_devices_updated([_device_payload("device-2", "Zenfone 11")])
    qtbot.wait(0)

    assert block._active_device_id is None
    assert block.available_device_list.currentItem() is None


def test_device_selection_block_clears_active_device_when_removed(qtbot) -> None:
    block = DeviceSelectionBlock()
    qtbot.addWidget(block)
    DeviceItem.add_to_list(block.available_device_list, id="device-1", text="Pixel 9")
    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "device-1", "Pixel 9")
    qtbot.wait(0)

    signals.DEVICE.RemoveDeviceRequested.emit("device-1")
    qtbot.wait(0)

    assert block._active_device_id is None
    assert block.available_device_list.count() == 0
