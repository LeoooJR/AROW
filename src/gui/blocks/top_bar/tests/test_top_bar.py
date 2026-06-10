"""Tests for the application top bar block."""

from __future__ import annotations

import pytest

from gui.blocks.top_bar import TopBar
from gui.colors import get_current_theme, set_current_theme
from gui.signals import signals

pytestmark = pytest.mark.usefixtures("qapp")


def _thumb_center(thumb) -> tuple[int, int]:
    rect = thumb.geometry()
    return rect.x() + rect.width() // 2, rect.y() + rect.height() // 2


def _button_center(button) -> tuple[int, int]:
    rect = button.geometry()
    return rect.x() + rect.width() // 2, rect.y() + rect.height() // 2


def test_top_bar_palette_thumb_aligns_with_dark_theme_at_startup(qtbot) -> None:
    previous_theme = get_current_theme()
    try:
        set_current_theme("dark")
        top_bar = TopBar()
        qtbot.addWidget(top_bar)
        top_bar.show()
        qtbot.wait(0)
        top_bar._update_palette_thumb_geometry()
        qtbot.wait(0)

        assert _thumb_center(top_bar.ui.palette_thumb) == _button_center(
            top_bar.ui.dark_palette_button
        )
    finally:
        set_current_theme(previous_theme)


def test_top_bar_palette_buttons_emit_theme_requests(qtbot) -> None:
    top_bar = TopBar()
    qtbot.addWidget(top_bar)

    with qtbot.waitSignal(signals.UI.UpdatePaletteSignal) as dark_signal:
        top_bar.dark_palette_button.click()
    with qtbot.waitSignal(signals.UI.UpdatePaletteSignal) as light_signal:
        top_bar.light_palette_button.click()

    assert dark_signal.args == ["dark"]
    assert light_signal.args == ["light"]


def test_top_bar_repeated_palette_clicks_keep_animation_valid(qtbot) -> None:
    top_bar = TopBar()
    qtbot.addWidget(top_bar)
    top_bar.show()
    qtbot.wait(0)

    top_bar.dark_palette_button.click()
    top_bar.light_palette_button.click()
    qtbot.wait(0)

    assert top_bar._palette_thumb_anim is not None


def test_top_bar_sidebar_buttons_emit_visibility_requests(qtbot) -> None:
    top_bar = TopBar()
    qtbot.addWidget(top_bar)

    with qtbot.waitSignal(signals.UI.LeftPanelsVisibilityRequested) as left_signal:
        top_bar.left_panel_visibility_request_button.click()
    with qtbot.waitSignal(signals.UI.RightPanelsVisibilityRequested) as right_signal:
        top_bar.right_panel_visibility_request_button.click()

    assert left_signal.args == [False]
    assert right_signal.args == [False]
