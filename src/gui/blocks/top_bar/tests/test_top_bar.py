"""Tests for the application top bar block."""

from __future__ import annotations

import pytest

from gui.blocks.top_bar import TopBar
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_top_bar_palette_buttons_emit_theme_requests(qtbot) -> None:
    top_bar = TopBar()
    qtbot.addWidget(top_bar)

    with qtbot.waitSignal(view_signals.UpdatePaletteSignal) as dark_signal:
        top_bar.dark_palette_button.click()
    with qtbot.waitSignal(view_signals.UpdatePaletteSignal) as light_signal:
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

    with qtbot.waitSignal(view_signals.LeftPanelsVisibilityRequested) as left_signal:
        top_bar.left_panel_visibility_request_button.click()
    with qtbot.waitSignal(view_signals.RightPanelsVisibilityRequested) as right_signal:
        top_bar.right_panel_visibility_request_button.click()

    assert left_signal.args == [False]
    assert right_signal.args == [False]
