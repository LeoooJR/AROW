"""Tests for adaptive welcome-tab layout."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

import gui.pages.welcome as welcome_module
from gui.constants.settings import Settings
from gui.pages import WelcomePage
from gui.pages.welcome_settings import welcome_settings

pytestmark = pytest.mark.usefixtures("qapp")


def test_welcome_panel_expanded_workspace_mode_caps_and_centers_content(qtbot) -> None:
    panel = WelcomePage()
    qtbot.addWidget(panel)
    panel.resize(1800, 1000)

    panel.set_expanded_workspace_mode(True)

    assert panel.ui.content_wrapper.maximumWidth() == (
        welcome_settings.EXPANDED_CONTENT_MAX_WIDTH
    )
    assert panel.ui.content_wrapper.minimumWidth() == (
        welcome_settings.EXPANDED_CONTENT_MAX_WIDTH
    )
    assert panel.layout().itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter


def test_welcome_panel_normal_workspace_mode_restores_expanding_content(qtbot) -> None:
    panel = WelcomePage()
    qtbot.addWidget(panel)

    panel.set_expanded_workspace_mode(True)
    panel.set_expanded_workspace_mode(False)

    assert panel.ui.content_wrapper.maximumWidth() == Settings.PANEL.UNBOUNDED_HEIGHT
    assert not panel.layout().itemAt(0).alignment() & Qt.AlignmentFlag.AlignHCenter


def test_welcome_panel_theme_refresh_targets_visible_top_card(
    monkeypatch, qtbot
) -> None:
    calls: list[tuple[str, str]] = []

    class _StubCard(QWidget):
        def __init__(self, role: str, parent=None) -> None:
            super().__init__(parent)
            self.role = role

        def apply_theme_icons(self, theme):  # type: ignore[no-untyped-def]
            calls.append((self.role, theme))

    class _StubConnectionCard(_StubCard):
        def __init__(self, parent=None) -> None:
            super().__init__("connection", parent)

    class _StubMilestoneCard(_StubCard):
        def __init__(self, parent=None) -> None:
            super().__init__("milestone", parent)

    class _StubBriefingCard(_StubCard):
        def __init__(self, parent=None) -> None:
            super().__init__("briefing", parent)

    class _StubRecentCard(_StubCard):
        def __init__(self, parent=None) -> None:
            super().__init__("recent", parent)

    monkeypatch.setattr(welcome_module, "OperatorReadinessBlock", _StubBriefingCard)
    monkeypatch.setattr(welcome_module, "ConnectionActionsBlock", _StubConnectionCard)
    monkeypatch.setattr(welcome_module, "MilestoneTargetBlock", _StubMilestoneCard)
    monkeypatch.setattr(welcome_module, "StartRecentBlock", _StubRecentCard)

    panel = WelcomePage()
    qtbot.addWidget(panel)
    panel.show()

    panel.apply_theme_icons("dark")
    assert ("connection", "dark") in calls
    assert ("milestone", "dark") not in calls

    calls.clear()
    panel.ui.connection_card.hide()
    panel.ui.milestone_card.show()

    panel.apply_theme_icons("light")
    assert ("connection", "light") not in calls
    assert ("milestone", "light") in calls
