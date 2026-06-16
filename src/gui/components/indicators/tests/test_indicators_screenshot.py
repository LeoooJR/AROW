"""Offscreen screenshot tests for indicator components."""

from __future__ import annotations

import pytest

from gui.components.indicators import (
    ConditionIndicator,
    DotStatusBadge,
    ProgressBar,
    StatusBadge,
)
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_condition_indicator_warning_screenshot(qtbot, tmp_path) -> None:
    indicator = ConditionIndicator()
    indicator.set_state("warning")
    capture_styled_widget_screenshot(
        qtbot,
        indicator,
        tmp_path=tmp_path,
        filename="condition_indicator_warning.png",
        width=120,
        height=120,
    )


@pytest.mark.screenshot
def test_progress_bar_screenshot(qtbot, tmp_path) -> None:
    progress = ProgressBar(
        None,
        minimum=0,
        maximum=2,
        value=1,
        step_labels=["Zero", "One", "Two"],
    )
    capture_styled_widget_screenshot(
        qtbot,
        progress,
        tmp_path=tmp_path,
        filename="progress_bar.png",
        width=420,
        height=120,
    )


@pytest.mark.screenshot
def test_status_badge_ready_screenshot(qtbot, tmp_path) -> None:
    badge = StatusBadge(text="Ready", kind="ready")
    capture_styled_widget_screenshot(
        qtbot,
        badge,
        tmp_path=tmp_path,
        filename="status_badge_ready.png",
        width=220,
        height=120,
    )


@pytest.mark.screenshot
def test_dot_status_badge_ready_screenshot(qtbot, tmp_path) -> None:
    badge = DotStatusBadge(text="ADB ready", kind="ready")
    capture_styled_widget_screenshot(
        qtbot,
        badge,
        tmp_path=tmp_path,
        filename="dot_status_badge_ready.png",
        width=260,
        height=120,
    )
