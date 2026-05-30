"""Tests for indicator components."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation

from gui.components.indicators import (
    ConditionIndicator,
    DotStatusBadge,
    ProgressBar,
    StatusBadge,
)

pytestmark = pytest.mark.usefixtures("qapp")


def test_condition_indicator_updates_state_and_pulse(qtbot) -> None:
    indicator = ConditionIndicator()
    qtbot.addWidget(indicator)

    indicator.set_state("warning")

    assert indicator.state() == "warning"
    assert indicator.property("indicator-state") == "warning"
    assert indicator._pulse_group is not None
    assert indicator._pulse_group.state() == QAbstractAnimation.State.Running

    indicator.set_state("valid")

    assert indicator.state() == "valid"
    assert indicator._pulse_group is None


def test_condition_indicator_accepts_unknown_state_without_crashing(qtbot) -> None:
    indicator = ConditionIndicator()
    qtbot.addWidget(indicator)

    indicator.set_state("unknown-custom-state")

    assert indicator.state() == "unknown-custom-state"
    assert indicator.property("indicator-state") == "unknown-custom-state"


def test_progress_bar_uses_step_labels_and_falls_back_out_of_range(qtbot) -> None:
    progress = ProgressBar(
        None, minimum=0, maximum=2, value=1, step_labels=["Zero", "One"]
    )
    qtbot.addWidget(progress)

    assert progress.format() == "1. One"

    progress.setValue(2)

    assert progress.format() == "%v"


def test_status_badge_keeps_default_stylesheet_property(qtbot) -> None:
    badge = StatusBadge(text="Not set", kind="not-set")
    qtbot.addWidget(badge)

    assert badge.objectName() == "status-badge"
    assert badge.property("status-badge") == "not-set"

    badge.set_status("Ready", "ready")

    assert badge.text() == "Ready"
    assert badge.kind() == "ready"
    assert badge.property("status-badge") == "ready"


def test_status_badge_accepts_custom_stylesheet_property(qtbot) -> None:
    badge = StatusBadge(
        text="PENDING",
        kind="muted",
        object_name="readiness-status-chip",
        property_name="readiness-status-chip",
    )
    qtbot.addWidget(badge)

    assert badge.objectName() == "readiness-status-chip"
    assert badge.property("readiness-status-chip") == "muted"
    assert badge.property("status-badge") is None

    badge.set_status("READY", "ready")

    assert badge.text() == "READY"
    assert badge.kind() == "ready"
    assert badge.property("readiness-status-chip") == "ready"
    assert badge.property("status-badge") is None


def test_dot_status_badge_renders_dot_and_label(qtbot) -> None:
    badge = DotStatusBadge(text="ADB ready", kind="ready")
    qtbot.addWidget(badge)

    assert badge.objectName() == "dot-status-badge"
    assert badge.property("dot-status-badge") == "ready"
    assert badge.ui.dot.objectName() == "dot-status-badge-dot"
    assert badge.ui.dot.property("dot-status-badge") == "ready"
    assert badge.ui.label.text() == "ADB ready"


def test_dot_status_badge_updates_status_and_repolishes(qtbot) -> None:
    badge = DotStatusBadge(text="Waiting", kind="muted")
    qtbot.addWidget(badge)

    badge.set_status("Needs attention", "warning")

    assert badge.kind() == "warning"
    assert badge.texts.label == "Needs attention"
    assert badge.ui.label.text() == "Needs attention"
    assert badge.property("dot-status-badge") == "warning"
    assert badge.ui.dot.property("dot-status-badge") == "warning"
