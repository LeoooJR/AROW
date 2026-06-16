"""Offscreen screenshot tests for label components."""

from __future__ import annotations

import pytest

from gui.components.labels import DemiBoldText, HelperText, LeadingIconLabel
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_helper_text_screenshot(qtbot, tmp_path) -> None:
    label = HelperText(None, "Secondary helper copy")
    capture_styled_widget_screenshot(
        qtbot,
        label,
        tmp_path=tmp_path,
        filename="helper_text.png",
        width=320,
        height=120,
    )


@pytest.mark.screenshot
def test_demi_bold_text_screenshot(qtbot, tmp_path) -> None:
    label = DemiBoldText(None, "Important title")
    capture_styled_widget_screenshot(
        qtbot,
        label,
        tmp_path=tmp_path,
        filename="demi_bold_text.png",
        width=320,
        height=120,
    )


@pytest.mark.screenshot
def test_leading_icon_label_screenshot(qtbot, tmp_path) -> None:
    label = LeadingIconLabel(
        None,
        GenericIcons.INFO,
        "Status message",
        font_size=Settings.FONT.SIZE_DEFAULT,
        font_weight=Settings.FONT.WEIGHT_NORMAL,
        icon_size=None,
        spacing=Settings.SPACING.ICON_SPACING,
    )
    capture_styled_widget_screenshot(
        qtbot,
        label,
        tmp_path=tmp_path,
        filename="leading_icon_label.png",
        width=360,
        height=120,
    )
