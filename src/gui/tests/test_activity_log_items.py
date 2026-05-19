"""
Tests for the custom activity-log list rows and panel API.

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import datetime as dt

import pytest
from PySide6.QtWidgets import QWidgetAction

from gui.logs import ActivityFilterOption, ActivityLogEntry, ActivityLogItem, LogPanel
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


def test_log_panel_public_api_updates_count_and_groups(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    panel.show()
    panel.clear_activities()

    first_id = panel.add_activity(
        "Device selected",
        "device",
        "success",
        timestamp=_NOW,
    )
    panel.add_activity(
        "Location set",
        "location",
        "info",
        timestamp=_NOW - dt.timedelta(days=1),
    )
    qtbot.wait(0)

    assert panel.ui.event_count_label.text() == "2 events"
    assert panel.ui.logs_list.count() == 4  # two date headers + two rows

    assert panel.remove_activity(first_id) is True
    assert panel.ui.event_count_label.text() == "1 event"
    assert panel.remove_activity("missing") is False


def test_log_panel_filter_hides_non_matching_entries(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    panel.clear_activities()
    panel.add_activity("Device selected", "device", "success", timestamp=_NOW)
    panel.add_activity("ADB stopped", "adb", "stop", timestamp=_NOW)

    panel.set_activity_filter(categories=["device"])

    assert panel.ui.event_count_label.text() == "1 event"
    visible_entries = [
        item.entry
        for item in panel.ui.logs_list.iter_items()
        if isinstance(item, ActivityLogItem)
    ]
    assert [entry.category for entry in visible_entries] == ["device"]


def test_log_panel_filter_menu_uses_custom_styled_rows(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    panel.setStyleSheet(stylesheet_light)

    option_widgets = [
        action.defaultWidget()
        for action in panel.ui.filter_menu.actions()
        if isinstance(action, QWidgetAction)
        and isinstance(action.defaultWidget(), ActivityFilterOption)
    ]

    assert panel.ui.filter_button.objectName() == "activity-log-filter-button"
    assert "QToolButton#activity-log-filter-button::menu-indicator" in stylesheet_light
    assert len(option_widgets) == 12
    assert all(
        widget.objectName() == "activity-log-filter-option" for widget in option_widgets
    )


def test_log_panel_keeps_file_display_under_activity_list(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)

    assert panel.ui.logs_wrapper.get_layout().indexOf(panel.ui.logs_list) >= 0
    assert panel.ui.logs_wrapper.get_layout().indexOf(panel.ui.file_display_widget) > (
        panel.ui.logs_wrapper.get_layout().indexOf(panel.ui.logs_list)
    )
    assert panel.ui.logs_wrapper.get_layout().indexOf(
        panel.ui.logs_list_helper_text
    ) > (panel.ui.logs_wrapper.get_layout().indexOf(panel.ui.file_display_widget))


def test_activity_item_size_hint_stays_within_narrow_panel(qtbot) -> None:
    panel = LogPanel()
    qtbot.addWidget(panel)
    panel.resize(340, 520)
    panel.show()
    panel.clear_activities()
    panel.add_activity(
        "A very long activity message that should wrap inside the log sidebar",
        "simulation",
        "warning",
        detail="Longer diagnostic copy stays readable without forcing horizontal scrolling.",
        timestamp=_NOW,
    )
    qtbot.wait(0)

    row = next(
        item
        for item in panel.ui.logs_list.iter_items()
        if isinstance(item, ActivityLogItem)
    )
    row._sync_size_hint()
    viewport_width = panel.ui.logs_list.viewport().width()

    assert viewport_width > 0
    assert row.sizeHint().width() <= viewport_width
