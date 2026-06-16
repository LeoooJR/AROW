"""Offscreen screenshot tests for top bar block."""

from __future__ import annotations

import pytest

from gui.blocks.top_bar import TopBar
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_top_bar_screenshot(qtbot, tmp_path) -> None:
    top_bar = TopBar()

    def _prepare(widget: TopBar) -> None:
        widget._update_palette_thumb_geometry()

    capture_styled_widget_screenshot(
        qtbot,
        top_bar,
        tmp_path=tmp_path,
        filename="top_bar.png",
        width=960,
        height=120,
        prepare=_prepare,
    )
