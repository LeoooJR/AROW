"""Offscreen screenshot tests for activity log block."""

from __future__ import annotations

import pytest

from gui.blocks.activity import ActivityLogBlock
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_activity_log_block_empty_screenshot(qtbot, tmp_path) -> None:
    block = ActivityLogBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="activity_log_block_empty.png",
        width=520,
        height=360,
        grab_root=True,
    )
