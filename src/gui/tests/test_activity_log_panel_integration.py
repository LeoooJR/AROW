"""
Integration tests for activity log panel behavior inside the main window shell.

Block-internal activity row and filtering behavior lives under
``gui.blocks.activity.tests``.
"""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import gui.ressources_rc
from gui.blocks.activity import ActivityLogItem
from gui.constants.fonts import register_bundled_fonts
from gui.constants.settings import Settings
from gui.routing import PageRoute
from gui.signals import signals
from gui.windows import MainWindow


def test_activity_log_resyncs_after_panel_visibility_sequence(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("AROW_GUI_TEST_SCREEN_SIZE", raising=False)
    app = QApplication.instance() or QApplication([])
    register_bundled_fonts()

    window = MainWindow()
    window.show()
    app.processEvents()
    workspace = window.ui.app_shell.ui.workspace
    signals.ADB_SERVER.ADBServerStarted.emit()

    workspace.set_left_panels_visibility(False)
    app.processEvents()
    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + 40)
    app.processEvents()
    workspace.set_left_panels_visibility(True)
    app.processEvents()
    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + 40)
    app.processEvents()
    workspace.ui.log_panel.refresh_layout(deferred=False)

    viewport_width = workspace.ui.log_panel.logs_list().viewport().width()
    file_display = workspace.ui.log_panel.file_display_widget()
    rows = [
        item
        for item in workspace.ui.log_panel.logs_list().iter_items()
        if isinstance(item, ActivityLogItem)
    ]

    assert viewport_width > 0
    assert rows
    assert (
        workspace.ui.router_wrapper.width() > workspace.ui.right_panels_wrapper.width()
    )
    assert all(row.sizeHint().width() <= viewport_width for row in rows)
    assert file_display._file_name_label.text().strip()
    assert file_display._file_type_label.isVisible()
    assert file_display._save_as_button.isVisible()
    assert window.grab().isNull() is False
    window.close()
    app.processEvents()


def test_welcome_workspace_mode_tracks_outer_sidebars(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("AROW_GUI_TEST_SCREEN_SIZE", raising=False)
    app = QApplication.instance() or QApplication([])
    register_bundled_fonts()

    window = MainWindow()
    window.show()
    app.processEvents()
    workspace = window.ui.app_shell.ui.workspace
    welcome = workspace.ui.router.page(PageRoute.WELCOME)

    workspace.set_left_panels_visibility(False)
    app.processEvents()
    assert welcome._expanded_workspace_mode is False

    workspace.set_right_panels_visibility(False)
    app.processEvents()
    assert welcome._expanded_workspace_mode is True

    workspace.set_left_panels_visibility(True)
    app.processEvents()
    assert welcome._expanded_workspace_mode is True

    QTest.qWait(Settings.ANIMATION.PANEL_VISIBILITY_DURATION + Settings.SPACING.SM + 20)
    app.processEvents()
    assert welcome._expanded_workspace_mode is False

    window.close()
    app.processEvents()
