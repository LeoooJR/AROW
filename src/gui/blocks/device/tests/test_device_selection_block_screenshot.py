"""Offscreen screenshot tests for device selection block."""

from __future__ import annotations

import pytest

from gui.blocks.device import DeviceSelectionBlock
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_device_selection_block_empty_screenshot(qtbot, tmp_path) -> None:
    block = DeviceSelectionBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="device_selection_block_empty.png",
        width=420,
        height=420,
    )


@pytest.mark.screenshot
def test_device_selection_block_seeded_screenshot(qtbot, tmp_path) -> None:
    block = DeviceSelectionBlock()
    block.add_list_items_placeholder()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="device_selection_block_seeded.png",
        width=420,
        height=520,
    )
