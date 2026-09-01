"""Full-window visual coverage for the managed shutdown overlay."""

from __future__ import annotations

import pytest

from gui.tests.screenshot_helpers import capture_styled_top_level_screenshot
from gui.windows import MainWindow

pytestmark = [pytest.mark.usefixtures("qapp"), pytest.mark.screenshot]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_shutdown_decision_overlay_full_window(qtbot, tmp_path, theme) -> None:
    window = MainWindow()

    def prepare(widget) -> None:
        widget._on_palette_update(theme)
        widget.show_background_shutdown_decision()

    capture_styled_top_level_screenshot(
        qtbot,
        window,
        tmp_path=tmp_path,
        filename=f"shutdown_overlay_1800x1000_{theme}.png",
        theme=theme,
        prepare=prepare,
    )


def test_shutdown_waiting_overlay_at_minimum_window(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("AROW_GUI_TEST_SCREEN_SIZE", "1280x720")
    window = MainWindow()

    def prepare(widget) -> None:
        widget._on_palette_update("light")
        widget.show_managed_shutdown_waiting()

    capture_styled_top_level_screenshot(
        qtbot,
        window,
        tmp_path=tmp_path,
        filename="shutdown_overlay_1280x720_waiting_light.png",
        theme="light",
        prepare=prepare,
    )
