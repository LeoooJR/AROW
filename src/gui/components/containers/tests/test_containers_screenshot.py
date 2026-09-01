"""Offscreen screenshot tests for container components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout

from gui.components.containers import (
    AuthentificationCard,
    GroupBox,
    PlaceHolder,
    ShutdownCard,
)
from gui.constants.icons import GenericIcons, icon_qt_path
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_group_box_screenshot(qtbot, tmp_path) -> None:
    child = QLabel("Inside the group")
    group = GroupBox(None, layout=QVBoxLayout(), widgets=[child], title="Devices")
    capture_styled_widget_screenshot(
        qtbot,
        group,
        tmp_path=tmp_path,
        filename="group_box_devices.png",
        width=420,
        height=180,
    )


@pytest.mark.screenshot
def test_placeholder_device_screenshot(qtbot, tmp_path) -> None:
    placeholder = PlaceHolder(
        None, "No device selected", icon=GenericIcons.DEVICE_PLACEHOLDER
    )
    capture_styled_widget_screenshot(
        qtbot,
        placeholder,
        tmp_path=tmp_path,
        filename="placeholder_device.png",
        width=360,
        height=260,
    )


@pytest.mark.screenshot
def test_authentification_card_screenshot(qtbot, tmp_path) -> None:
    card = AuthentificationCard(
        None,
        title="Pair device",
        icon_path=icon_qt_path(GenericIcons.DEVICE),
        description="Enter the pairing details shown on your phone.",
    )
    capture_styled_widget_screenshot(
        qtbot,
        card,
        tmp_path=tmp_path,
        filename="authentification_card.png",
        width=520,
        height=420,
    )


@pytest.mark.screenshot
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("mode", ["decision", "waiting"])
def test_shutdown_card_screenshot(qtbot, tmp_path, theme, mode) -> None:
    card = ShutdownCard()

    def prepare(widget) -> None:
        widget.apply_theme_icons(theme)
        if mode == "decision":
            widget.show_decision(
                "The Android connection is still closing. You can keep waiting "
                "or force AROW to close."
            )
        else:
            widget.show_waiting()

    capture_styled_widget_screenshot(
        qtbot,
        card,
        tmp_path=tmp_path,
        filename=f"shutdown_card_{mode}_{theme}.png",
        theme=theme,
        width=568,
        height=460,
        prepare=prepare,
    )
