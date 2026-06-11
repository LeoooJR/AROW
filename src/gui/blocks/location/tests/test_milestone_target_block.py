"""Tests for location milestone target blocks."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from gui.blocks.location import MilestoneMetadataItem, MilestoneTargetBlock
from gui.signals import signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_milestone_target_block_seeds_not_set_placeholders(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    assert block.ui.title.text() == block.texts.title
    assert block.ui.status_badge.text() == "Not set"
    assert block.ui.status_badge.kind() == "not-set"
    assert block.ui.status_badge.property("status-badge") == "not-set"
    assert block.ui.line_item.ui.value.text() == "--"
    assert block.ui.km_item.ui.value.text() == "--"
    assert block.ui.longitude_item.ui.value.text() == "--"
    assert block.ui.latitude_item.ui.value.text() == "--"
    assert block.ui.type_item.ui.value.text() == "--"
    assert block.ui.source_item.ui.value.text() == "--"


def test_milestone_target_block_updates_values_and_keeps_missing_placeholders(
    qtbot,
) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.set_target_values(
        line="Ligne 830000",
        km="128.450",
        longitude=2.3522,
        type_="Kilomètre",
        source="",
    )

    assert block.ui.line_item.ui.value.text() == "Ligne 830000"
    assert block.ui.km_item.ui.value.text() == "128.450"
    assert block.ui.longitude_item.raw_value == "2.352200"
    assert block.ui.latitude_item.ui.value.text() == "--"
    assert block.ui.type_item.ui.value.text() == "Kilomètre"
    assert block.ui.source_item.ui.value.text() == "--"


def test_milestone_target_block_updates_status_and_repolishes_badge(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.set_target_values(status_text="Ready", status_kind="ready")

    assert block.ui.status_badge.text() == "Ready"
    assert block.ui.status_badge.kind() == "ready"
    assert block.ui.status_badge.property("status-badge") == "ready"


def test_milestone_target_block_populates_placeholders_from_debug_signal(
    qtbot,
) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    signals.UI.UiConstraintsDisabled.emit()
    qtbot.wait(0)

    assert block.ui.status_badge.text() == "Ready"
    assert block.ui.status_badge.kind() == "ready"
    assert block.ui.line_item.raw_value == block.texts.placeholder_line
    assert block.ui.km_item.raw_value == block.texts.placeholder_km
    assert block.ui.longitude_item.raw_value == (
        f"{block.texts.placeholder_longitude:.6f}"
    )
    assert block.ui.latitude_item.raw_value == f"{block.texts.placeholder_latitude:.6f}"
    assert block.ui.type_item.raw_value == block.texts.placeholder_type
    assert block.ui.source_item.raw_value == block.texts.placeholder_source


def test_milestone_target_block_set_placeholder_values_uses_text_fields(
    qtbot,
) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.set_placeholder_values()

    assert block.ui.line_item.raw_value == block.texts.placeholder_line
    assert block.ui.source_item.raw_value == block.texts.placeholder_source
    assert block.ui.status_badge.property("status-badge") == "ready"


def test_milestone_target_block_bounds_coordinate_precision(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.set_target_values(
        longitude=2.123456789123,
        latitude="48.987654321987",
    )

    assert block.ui.longitude_item.raw_value == "2.123457"
    assert block.ui.latitude_item.raw_value == "48.987654"


def test_milestone_metadata_item_elides_long_values_in_narrow_width(qtbot) -> None:
    item = MilestoneMetadataItem(None, key="Source")
    qtbot.addWidget(item)
    long_value = "SNCF-OPEN-DATA:pk-gps-v2026-with-extra-edge-case-label"

    item.setFixedWidth(120)
    item.resize(120, 24)
    item.show()
    qtbot.wait(0)
    item.set_value(long_value)
    qtbot.wait(10)

    assert item.raw_value == long_value
    assert item.ui.value.text() != long_value
    assert item.ui.value.text().endswith("…")


def test_milestone_target_button_emits_target_selection_request(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)
    spy = QSignalSpy(signals.UI.TargetSelectionRequested)

    qtbot.mouseClick(block.ui.target_button, Qt.MouseButton.LeftButton)

    assert spy.count() == 1


def test_milestone_target_button_uses_theme_aware_crosshair_icon(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.apply_theme_icons("dark")

    assert block.ui.target_button._icon is not None
