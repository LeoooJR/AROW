"""
Tests for full-window offscreen rendering support.

The screenshots path needs ``MainWindow`` to construct even when Qt's offscreen
platform does not expose a primary screen.
"""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import gui.ressources_rc
from gui.fonts import register_bundled_fonts
from gui.logs import ActivityLogItem
from gui.settings import Settings
from gui.window import (
    _DEFAULT_OFFSCREEN_SCREEN_SIZE,
    _main_window_screen_size,
    MainWindow,
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

    window = MainWindow(ui_constraints_disabled=True)
    window.show()
    app.processEvents()

    pixmap = window.grab()

    assert window.size() == _DEFAULT_OFFSCREEN_SCREEN_SIZE
    assert pixmap.isNull() is False
    assert pixmap.size() == _DEFAULT_OFFSCREEN_SCREEN_SIZE
    window.close()
    app.processEvents()


def test_activity_log_resyncs_after_panel_visibility_sequence(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("AROW_GUI_TEST_SCREEN_SIZE", raising=False)
    app = QApplication.instance() or QApplication([])
    register_bundled_fonts()

    window = MainWindow(ui_constraints_disabled=True)
    window.show()
    app.processEvents()
    body = window.ui.container.ui.body

    body.set_host_panel_visibility(False)
    app.processEvents()
    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + 40)
    app.processEvents()
    body.set_left_panels_visibility(False)
    app.processEvents()
    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + 40)
    app.processEvents()
    body.set_left_panels_visibility(True)
    app.processEvents()
    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + 40)
    app.processEvents()
    body.ui.log_panel.refresh_layout(deferred=False)

    viewport_width = body.ui.log_panel.ui.logs_list.viewport().width()
    file_display = body.ui.log_panel.ui.file_display_widget
    rows = [
        item
        for item in body.ui.log_panel.ui.logs_list.iter_items()
        if isinstance(item, ActivityLogItem)
    ]

    assert viewport_width > 0
    assert rows
    assert body.ui.tabs_wrapper.width() > body.ui.right_panels_wrapper.width()
    assert all(row.sizeHint().width() <= viewport_width for row in rows)
    assert file_display._file_name_label.text().strip()
    assert file_display._file_type_label.isVisible()
    assert file_display._save_as_button.isVisible()
    assert window.grab().isNull() is False
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
