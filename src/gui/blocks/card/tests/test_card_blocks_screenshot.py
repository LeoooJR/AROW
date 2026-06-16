"""Offscreen screenshot tests for card blocks."""

from __future__ import annotations

import pytest

from gui.blocks.card import BridgeStatusCardBlock, IdentityCardBlock
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_identity_card_block_placeholder_screenshot(qtbot, tmp_path) -> None:
    card = IdentityCardBlock()
    capture_styled_widget_screenshot(
        qtbot,
        card,
        tmp_path=tmp_path,
        filename="identity_card_block_placeholder.png",
        width=460,
        height=320,
    )


@pytest.mark.screenshot
def test_bridge_status_card_block_placeholder_screenshot(qtbot, tmp_path) -> None:
    card = BridgeStatusCardBlock()
    capture_styled_widget_screenshot(
        qtbot,
        card,
        tmp_path=tmp_path,
        filename="bridge_status_card_block_placeholder.png",
        width=460,
        height=320,
    )
