"""Offscreen screenshot tests for media components."""

from __future__ import annotations

from pathlib import Path

import pytest

from gui.components.media import SVG, Image
from gui.icons import GenericIcons, icon_qt_path
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")

_LOGO_PATH = Path(__file__).resolve().parents[4] / "statics" / "logo.png"


@pytest.mark.screenshot
def test_svg_device_icon_screenshot(qtbot, tmp_path) -> None:
    svg = SVG(icon_qt_path(GenericIcons.DEVICE))
    svg.setFixedSize(64, 64)
    capture_styled_widget_screenshot(
        qtbot,
        svg,
        tmp_path=tmp_path,
        filename="svg_device_icon.png",
        width=160,
        height=160,
    )


@pytest.mark.screenshot
def test_image_logo_screenshot(qtbot, tmp_path) -> None:
    image = Image(None, str(_LOGO_PATH))
    image.setFixedSize(96, 96)
    capture_styled_widget_screenshot(
        qtbot,
        image,
        tmp_path=tmp_path,
        filename="image_logo.png",
        width=180,
        height=180,
    )
