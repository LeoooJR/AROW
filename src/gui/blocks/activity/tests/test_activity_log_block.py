"""
Tests for the activity log block and custom activity rows.

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import datetime as dt

import pytest
from PySide6.QtWidgets import QWidgetAction

import gui.blocks.activity.activity_log as activity_log_module
from gui.blocks.activity import (
    ActivityFilterOption,
    ActivityLogBlock,
    ActivityLogEntry,
    ActivityLogItem,
)
from gui.stylesheet import stylesheet_light

pytestmark = pytest.mark.usefixtures("qapp")

_NOW = dt.datetime(2026, 5, 18, 12, 47, 26)


def _entry(**overrides) -> ActivityLogEntry:  # type: ignore[no-untyped-def]
    defaults = {
        "id": "activity-1",
        "timestamp": _NOW,
        "category": "simulation",
        "level": "start",
        "message": "Simulation started",
        "detail": None,
        "metadata": {"device": "Pixel 8 Pro"},
    }
    defaults.update(overrides)
    return ActivityLogEntry(**defaults)


def test_activity_item_exposes_entry_and_detail(qtbot) -> None:
    item = ActivityLogItem(
        _entry(
            detail="Fake location is now streamed to the selected Android device.",
            level="success",
        )
    )
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    assert item.entry.message == "Simulation started"
    assert item.ui.detail_label.isHidden() is False
    assert "streamed" in item.ui.detail_label.text()
    assert item.ui.level_label.text() == "OK"


def test_activity_item_selection_and_hover_properties(qtbot) -> None:
    item = ActivityLogItem(_entry())
    qtbot.addWidget(item.ui.row)
    qtbot.wait(0)

    item.set_selected(True)
    item.set_hovered(True)

    assert item.ui.row.property("selected") is True
    assert item.ui.row.property("hovered") is True


def test_activity_log_block_theme_refresh_updates_activity_row_icons(
    monkeypatch, qtbot
) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)
    block.clear_activities()
    block.add_activity("Device selected", "device", "success", timestamp=_NOW)

    calls = []
    original = activity_log_module.icon_qt_path_for_theme

    def spy_icon_path(theme, member):  # type: ignore[no-untyped-def]
        calls.append((theme, member))
        return original(theme, member)

    monkeypatch.setattr(activity_log_module, "icon_qt_path_for_theme", spy_icon_path)

    block.apply_theme_icons("dark")

    assert ("dark", ActivityLogItem._CATEGORY_ICON["device"]) in calls


def test_activity_log_block_public_api_updates_count_and_groups(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)
    block.show()
    block.clear_activities()

    first_id = block.add_activity(
        "Device selected",
        "device",
        "success",
        timestamp=_NOW,
    )
    block.add_activity(
        "Location set",
        "location",
        "info",
        timestamp=_NOW - dt.timedelta(days=1),
    )
    qtbot.wait(0)

    assert block.ui.event_count_label.text() == "2 events"
    assert block.logs_list().count() == 4  # two date headers + two rows

    assert block.remove_activity(first_id) is True
    assert block.ui.event_count_label.text() == "1 event"
    assert block.remove_activity("missing") is False


def test_activity_log_block_filter_hides_non_matching_entries(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)
    block.clear_activities()
    block.add_activity("Device selected", "device", "success", timestamp=_NOW)
    block.add_activity("ADB stopped", "adb", "stop", timestamp=_NOW)

    block.set_activity_filter(categories=["device"])

    assert block.ui.event_count_label.text() == "1 event"
    visible_entries = [
        item.entry
        for item in block.logs_list().iter_items()
        if isinstance(item, ActivityLogItem)
    ]
    assert [entry.category for entry in visible_entries] == ["device"]


def test_activity_log_block_filter_menu_uses_custom_styled_rows(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)
    block.setStyleSheet(stylesheet_light)

    option_widgets = [
        action.defaultWidget()
        for action in block.ui.filter_menu.actions()
        if isinstance(action, QWidgetAction)
        and isinstance(action.defaultWidget(), ActivityFilterOption)
    ]

    assert block.ui.filter_button.objectName() == "activity-log-filter-button"
    assert "QToolButton#activity-log-filter-button::menu-indicator" in stylesheet_light
    assert len(option_widgets) == 12
    assert all(
        widget.objectName() == "activity-log-filter-option" for widget in option_widgets
    )


def test_activity_log_block_keeps_file_display_under_activity_list(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)

    assert block.ui.logs_wrapper.get_layout().indexOf(block.logs_list()) >= 0
    assert block.ui.logs_wrapper.get_layout().indexOf(block.file_display_widget()) > (
        block.ui.logs_wrapper.get_layout().indexOf(block.logs_list())
    )
    assert block.ui.logs_wrapper.get_layout().indexOf(
        block.ui.logs_list_helper_text
    ) > (block.ui.logs_wrapper.get_layout().indexOf(block.file_display_widget()))


def test_activity_item_size_hint_stays_within_narrow_block(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)
    block.resize(340, 520)
    block.show()
    block.clear_activities()
    block.add_activity(
        "A very long activity message that should wrap inside the log sidebar",
        "simulation",
        "warning",
        detail="Longer diagnostic copy stays readable without forcing horizontal scrolling.",
        timestamp=_NOW,
    )
    qtbot.wait(0)

    row = next(
        item for item in block.logs_list().iter_items() if isinstance(item, ActivityLogItem)
    )
    row._sync_size_hint()
    viewport_width = block.logs_list().viewport().width()

    assert viewport_width > 0
    assert row.sizeHint().width() <= viewport_width


def test_activity_log_block_rejects_unknown_category(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)

    with pytest.raises(ValueError, match="Unknown activity category"):
        block.add_activity("Mystery", "unknown", "info")  # type: ignore[arg-type]


def test_activity_log_block_rejects_unknown_level(qtbot) -> None:
    block = ActivityLogBlock()
    qtbot.addWidget(block)

    with pytest.raises(ValueError, match="Unknown activity level"):
        block.add_activity("Mystery", "device", "mystery")  # type: ignore[arg-type]
