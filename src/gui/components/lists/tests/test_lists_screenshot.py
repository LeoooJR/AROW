"""Offscreen screenshot tests for list components."""

from __future__ import annotations

import pytest

from gui.components.lists import List
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_list_sample_rows_screenshot(qtbot, tmp_path) -> None:
    list_widget = List(None, items=["Pixel 8 Pro", "Zenfone 11", "Galaxy S24"])
    capture_styled_widget_screenshot(
        qtbot,
        list_widget,
        tmp_path=tmp_path,
        filename="list_sample_rows.png",
        width=360,
        height=220,
    )
