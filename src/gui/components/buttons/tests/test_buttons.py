"""Tests for button components."""

from __future__ import annotations

import pytest

from gui.components.buttons import Button, ToolButton, WalkthroughButton
from gui.components.buttons.button_settings import button_settings
from gui.constants.icons import GenericIcons, OperatingSystemIcons

pytestmark = pytest.mark.usefixtures("qapp")


def test_button_and_tool_button_apply_basic_properties(qtbot) -> None:
    button = Button(None, "Run", icon=GenericIcons.PLAY)
    tool_button = ToolButton(None, icon=GenericIcons.PLUS, tooltip="Add")
    qtbot.addWidget(button)
    qtbot.addWidget(tool_button)

    assert button.text() == "Run"
    assert button.property("button") is True
    assert button.height() == button_settings.BUTTON_HEIGHT
    assert tool_button.toolTip() == "Add"
    assert tool_button.property("tool-button") is True


def test_tool_button_ignores_empty_icon_update(qtbot) -> None:
    button = ToolButton(None, icon=GenericIcons.PLUS)
    qtbot.addWidget(button)
    before = button._icon

    button.set_icon(None)

    assert button._icon == before


def test_walkthrough_button_builds_internal_labels_and_rejects_missing_icon(
    qtbot,
) -> None:
    button = WalkthroughButton(
        None,
        "Connect over USB",
        leading_icon=OperatingSystemIcons.ANDROID,
        trailing_icon=GenericIcons.HAND_INDEX,
    )
    qtbot.addWidget(button)

    assert button.text() == ""
    assert button.ui.label.text() == "Connect over USB"
    assert button.ui.leading_svg.property("svg") is True

    with pytest.raises((TypeError, ValueError)):
        WalkthroughButton(
            None,  # type: ignore[arg-type]
            "Broken",
            leading_icon=None,  # type: ignore[arg-type]
            trailing_icon=None,  # type: ignore[arg-type]
        )
