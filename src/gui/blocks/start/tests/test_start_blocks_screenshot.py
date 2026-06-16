"""Offscreen screenshot tests for start blocks."""

from __future__ import annotations

import pytest

from gui.blocks.start import (
    ConnectionActionsBlock,
    OperatorReadinessBlock,
    StartRecentBlock,
    WalkthroughBlock,
)
from gui.signals import signals
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_connection_actions_block_screenshot(qtbot, tmp_path) -> None:
    block = ConnectionActionsBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="connection_actions_block.png",
        width=420,
        height=220,
    )


@pytest.mark.screenshot
def test_operator_readiness_block_screenshot(qtbot, tmp_path) -> None:
    block = OperatorReadinessBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="operator_readiness_block.png",
        width=460,
        height=260,
    )


@pytest.mark.screenshot
def test_start_recent_block_demo_screenshot(qtbot, tmp_path) -> None:
    block = StartRecentBlock()
    signals.UI.UiConstraintsDisabled.emit()
    qtbot.wait(0)
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="start_recent_block_demo.png",
        width=520,
        height=320,
    )


@pytest.mark.screenshot
def test_walkthrough_block_screenshot(qtbot, tmp_path) -> None:
    block = WalkthroughBlock()
    capture_styled_widget_screenshot(
        qtbot,
        block,
        tmp_path=tmp_path,
        filename="walkthrough_block.png",
        width=560,
        height=360,
    )
