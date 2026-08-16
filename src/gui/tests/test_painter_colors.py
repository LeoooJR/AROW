"""Tests for palette-to-QPainter color conversion."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from gui.constants.colors import Colors, get_palette, qcolor_from_css

pytestmark = pytest.mark.usefixtures("qapp")


def test_qcolor_from_css_parses_hex_values() -> None:
    color = qcolor_from_css("#FF6A00")

    assert color.isValid()
    assert color.red() == 255
    assert color.green() == 106
    assert color.blue() == 0
    assert color.alpha() == 255


def test_qcolor_from_css_parses_transparent() -> None:
    color = qcolor_from_css("transparent")

    assert color.isValid()
    assert color.alpha() == 0


def test_qcolor_from_css_parses_rgba_with_fractional_alpha() -> None:
    color = qcolor_from_css("rgba(255, 106, 0, 0.18)")

    assert color.isValid()
    assert color.red() == 255
    assert color.green() == 106
    assert color.blue() == 0
    assert color.alpha() == 46


def test_qcolor_from_css_parses_rgb_without_alpha() -> None:
    color = qcolor_from_css("rgb(255, 106, 0)")

    assert color.isValid()
    assert color.red() == 255
    assert color.green() == 106
    assert color.blue() == 0
    assert color.alpha() == 255


def test_qcolor_from_css_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="Unsupported palette color value"):
        qcolor_from_css("not-a-color")


@pytest.mark.parametrize(
    ("token", "expected_alpha"),
    [
        (Colors.PRIMARY_SOFT, 46),
        (Colors.PRIMARY_BORDER, 87),
    ],
)
def test_dark_palette_rgba_tokens_convert_for_painter(
    token: Colors, expected_alpha: int
) -> None:
    palette_value = token.value.for_theme("dark")
    color = qcolor_from_css(palette_value)

    assert color.isValid()
    assert color.alpha() == expected_alpha


def test_device_required_glyph_palette_colors_are_valid_in_dark_mode() -> None:
    palette = get_palette("dark")

    for value in (palette.PRIMARY_SOFT, palette.PRIMARY_BORDER):
        color = qcolor_from_css(value)
        assert color.isValid()
        assert 0 < color.alpha() < 255


def test_map_loading_glyph_palette_colors_are_valid_in_dark_mode() -> None:
    palette = get_palette("dark")

    for value in (palette.PRIMARY, palette.PRIMARY_SOFT):
        color = qcolor_from_css(value)
        assert color.isValid()
        if value.startswith("rgba("):
            assert 0 < color.alpha() < 255
        else:
            assert color.alpha() == 255


def test_device_discovery_glyph_palette_colors_are_valid_in_dark_mode() -> None:
    palette = get_palette("dark")

    for value in (palette.PRIMARY_SOFT, palette.PRIMARY_BORDER):
        color = qcolor_from_css(value)
        assert color.isValid()
        assert 0 < color.alpha() < 255


def test_qcolor_direct_constructor_fails_for_css_rgba() -> None:
    direct = QColor("rgba(255, 106, 0, 0.18)")

    assert not direct.isValid() or direct.alpha() == 255
