"""Tests for toast feedback component."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWidgets import QWidget

from gui.components.feedback import Toast

pytestmark = pytest.mark.usefixtures("qapp")


def test_toast_shows_message_and_starts_fade(qtbot) -> None:
    parent = QWidget()
    toast = Toast(parent, "Saved", level="success", duration=1000)
    qtbot.addWidget(parent)
    qtbot.addWidget(toast)

    assert toast.texts.message == "Saved"
    assert toast.texts.level == "success"
    assert toast._auto_close_timer.isActive() is True
    assert toast._fade_in.state() == QAbstractAnimation.State.Running

    toast.close()


def test_toast_unknown_level_falls_back_without_crashing(qtbot) -> None:
    parent = QWidget()
    toast = Toast(parent, "Mystery", level="custom", duration=1)
    qtbot.addWidget(parent)
    qtbot.addWidget(toast)

    assert toast.texts.level == "custom"

    toast.close()
    assert toast._auto_close_timer.isActive() is False
