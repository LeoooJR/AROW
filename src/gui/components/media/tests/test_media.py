"""Tests for media rendering components."""

from __future__ import annotations

import pytest

from gui.components.media import SVG, Image, get_svg_size
from gui.components.media.svg_settings import svg_settings

pytestmark = pytest.mark.usefixtures("qapp")


def test_svg_size_scales_from_font_size() -> None:
    small = get_svg_size(12)
    large = get_svg_size(24)

    assert small.width() == int(svg_settings.MULTIPLIER_SMALL * 12)
    assert large.width() == int(svg_settings.MULTIPLIER_LARGE * 24)
    assert small.width() == small.height()


def test_svg_accepts_invalid_path_without_crashing(qtbot) -> None:
    svg = SVG("/missing/icon.svg")
    qtbot.addWidget(svg)

    svg.set_path("/still/missing/icon.svg")

    assert svg.path == "/still/missing/icon.svg"
    assert svg.property("svg") is True


def test_image_handles_missing_and_replaced_pixmap_paths(qtbot) -> None:
    image = Image(None, "/missing/image.png")
    qtbot.addWidget(image)

    assert image.property("image") is True
    assert image.pixmap().isNull() is True

    image.set_pixmap_path("/also/missing.png")

    assert image.pixmap().isNull() is True
