"""Tests for location milestone target blocks."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from gui.blocks.location import MilestoneTargetBlock
from gui.signals import view_signals

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
    assert block.ui.longitude_item.ui.value.text() == "2.3522"
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


def test_milestone_target_button_emits_target_selection_request(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)
    spy = QSignalSpy(view_signals.TargetSelectionRequested)

    qtbot.mouseClick(block.ui.target_button, Qt.MouseButton.LeftButton)

    assert spy.count() == 1


def test_milestone_target_button_uses_theme_aware_crosshair_icon(qtbot) -> None:
    block = MilestoneTargetBlock()
    qtbot.addWidget(block)

    block.apply_theme_icons("dark")

    assert block.ui.target_button._icon is not None
