"""Offscreen screenshot tests for file display components."""

from __future__ import annotations

import pytest

from gui.components.file_display import File
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_file_display_log_screenshot(qtbot, tmp_path) -> None:
    file_widget = File(
        None,
        "kilometer-marker_128450.log",
        "log",
        file_save=True,
        date_text="Last opened 2026-05-26",
    )
    capture_styled_widget_screenshot(
        qtbot,
        file_widget,
        tmp_path=tmp_path,
        filename="file_display_log.png",
        width=420,
        height=120,
    )
