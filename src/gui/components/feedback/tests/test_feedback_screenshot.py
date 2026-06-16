"""Offscreen screenshot tests for feedback components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from gui.components.feedback import Toast
from gui.tests.screenshot_helpers import capture_styled_top_level_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


def _freeze_toast_timers(toast: Toast) -> None:
    toast._auto_close_timer.stop()
    toast._fade_in.stop()


@pytest.mark.screenshot
def test_toast_success_screenshot(qtbot, tmp_path) -> None:
    parent = QWidget()
    toast = Toast(parent, "Saved", level="success", duration=999_999)
    capture_styled_top_level_screenshot(
        qtbot,
        toast,
        tmp_path=tmp_path,
        filename="toast_success.png",
        prepare=_freeze_toast_timers,
    )
