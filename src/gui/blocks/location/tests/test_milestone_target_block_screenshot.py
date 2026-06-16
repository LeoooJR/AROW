"""Offscreen screenshot tests for milestone target block."""

from __future__ import annotations

import pytest

from gui.blocks.location import MilestoneTargetBlock
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_milestone_target_block_placeholder_screenshot(qtbot, tmp_path) -> None:
    block = MilestoneTargetBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="milestone_target_block_placeholder.png",
        width=460,
        height=360,
    )


@pytest.mark.screenshot
def test_milestone_target_block_filled_screenshot(qtbot, tmp_path) -> None:
    block = MilestoneTargetBlock()
    block.set_target_values(
        line="Ligne 830000",
        km="128.450",
        longitude=2.3522,
        latitude=48.8566,
        type_="Kilomètre",
        source="Dataset",
        status_text="Ready",
        status_kind="ready",
    )
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="milestone_target_block_filled.png",
        width=460,
        height=360,
    )
