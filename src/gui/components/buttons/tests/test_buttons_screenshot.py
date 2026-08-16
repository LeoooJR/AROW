"""Offscreen screenshot tests for button components."""

from __future__ import annotations

import pytest

from gui.components.buttons import Button, ToolButton, WalkthroughButton
from gui.constants.icons import GenericIcons, OperatingSystemIcons
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_button_play_icon_screenshot(qtbot, tmp_path) -> None:
    button = Button(None, "Run", icon=GenericIcons.PLAY)
    capture_styled_widget_screenshot(
        qtbot,
        button,
        tmp_path=tmp_path,
        filename="button_play.png",
        width=220,
        height=120,
    )


@pytest.mark.screenshot
def test_tool_button_plus_icon_screenshot(qtbot, tmp_path) -> None:
    button = ToolButton(None, icon=GenericIcons.PLUS, tooltip="Add")
    capture_styled_widget_screenshot(
        qtbot,
        button,
        tmp_path=tmp_path,
        filename="tool_button_plus.png",
        width=120,
        height=120,
    )


@pytest.mark.screenshot
def test_walkthrough_button_android_hand_screenshot(qtbot, tmp_path) -> None:
    button = WalkthroughButton(
        None,
        "Connect over USB",
        leading_icon=OperatingSystemIcons.ANDROID,
        trailing_icon=GenericIcons.HAND_INDEX,
    )
    capture_styled_widget_screenshot(
        qtbot,
        button,
        tmp_path=tmp_path,
        filename="walkthrough_button_android_hand.png",
        width=520,
        height=140,
    )
