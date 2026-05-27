"""Tests for adaptive welcome-tab layout."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from gui.settings import Settings
from gui.welcome import WelcomePanel

pytestmark = pytest.mark.usefixtures("qapp")


def test_welcome_panel_expanded_workspace_mode_caps_and_centers_content(qtbot) -> None:
    panel = WelcomePanel()
    qtbot.addWidget(panel)
    panel.resize(1800, 1000)

    panel.set_expanded_workspace_mode(True)

    assert panel.ui.content_wrapper.maximumWidth() == (
        Settings.WELCOME.EXPANDED_CONTENT_MAX_WIDTH
    )
    assert panel.ui.content_wrapper.minimumWidth() == (
        Settings.WELCOME.EXPANDED_CONTENT_MAX_WIDTH
    )
    assert panel.layout().itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter


def test_welcome_panel_normal_workspace_mode_restores_expanding_content(qtbot) -> None:
    panel = WelcomePanel()
    qtbot.addWidget(panel)

    panel.set_expanded_workspace_mode(True)
    panel.set_expanded_workspace_mode(False)

    assert panel.ui.content_wrapper.maximumWidth() == Settings.PANEL.UNBOUNDED_HEIGHT
    assert not panel.layout().itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter
