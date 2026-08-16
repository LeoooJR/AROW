"""
Tests for full-window offscreen rendering support.

The screenshots path needs ``MainWindow`` to construct even when Qt's offscreen
platform does not expose a primary screen.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

import gui.ressources_rc
from gui.constants.fonts import register_bundled_fonts
from gui.windows.main_window import (
    _DEFAULT_OFFSCREEN_SCREEN_SIZE,
    MainWindow,
    _main_window_screen_size,
)


def _force_no_primary_screen(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: None))


def test_main_window_can_be_grabbed_offscreen_without_primary_screen(
    monkeypatch,
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("AROW_GUI_TEST_SCREEN_SIZE", raising=False)
    _force_no_primary_screen(monkeypatch)
    app = QApplication.instance() or QApplication([])
    register_bundled_fonts()

    window = MainWindow()
    window.show()
    app.processEvents()

    pixmap = window.grab()

    assert window.size() == _DEFAULT_OFFSCREEN_SCREEN_SIZE
    assert pixmap.isNull() is False
    assert pixmap.size() == _DEFAULT_OFFSCREEN_SCREEN_SIZE
    window.close()
    app.processEvents()


def test_main_window_offscreen_size_can_be_configured(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("AROW_GUI_TEST_SCREEN_SIZE", "1600x900")
    _force_no_primary_screen(monkeypatch)

    screen_size = _main_window_screen_size()

    assert screen_size.width() == 1600
    assert screen_size.height() == 900


def test_malformed_offscreen_size_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("AROW_GUI_TEST_SCREEN_SIZE", "large-ish")
    _force_no_primary_screen(monkeypatch)

    assert _main_window_screen_size() == _DEFAULT_OFFSCREEN_SCREEN_SIZE
