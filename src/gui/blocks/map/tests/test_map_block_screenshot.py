"""Offscreen screenshot tests for map block."""

from __future__ import annotations

import pytest

from gui.blocks.map import MapBlock
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_map_block_device_required_placeholder_screenshot(qtbot, tmp_path) -> None:
    block = MapBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="map_block_device_required_placeholder.png",
        width=720,
        height=520,
    )


@pytest.mark.screenshot
def test_map_block_map_loading_placeholder_screenshot(qtbot, tmp_path) -> None:
    block = MapBlock()
    block.show_map_loading_placeholder()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="map_block_map_loading_placeholder.png",
        width=720,
        height=520,
    )


@pytest.mark.screenshot
def test_map_block_map_render_failed_placeholder_screenshot(qtbot, tmp_path) -> None:
    block = MapBlock()
    block.show_map_render_failed_placeholder()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="map_block_map_render_failed_placeholder.png",
        width=720,
        height=520,
    )
