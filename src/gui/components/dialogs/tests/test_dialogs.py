"""Tests for dialog components."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFileDialog, QMessageBox

import gui.ressources_rc  # noqa: F401 — register Qt resources for icon pixmaps
from gui.components.dialogs import (
    FileOpenDialog,
    FileSaveDialog,
    QuestionDialog,
    WarningDialog,
)
from gui.components.dialogs.dialog_settings import dialog_settings
from gui.icons import GenericIcons

pytestmark = pytest.mark.usefixtures("qapp")


def _dialog_screenshot_dir(tmp_path: Path) -> Path:
    """Return persistent screenshot dir from env or pytest tmp_path."""
    output_dir = os.environ.get("AROW_DIALOG_SCREENSHOT_DIR")
    if output_dir:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return tmp_path


def test_file_dialogs_configure_open_and_save_modes(qtbot) -> None:
    open_dialog = FileOpenDialog()
    save_dialog = FileSaveDialog()
    qtbot.addWidget(open_dialog)
    qtbot.addWidget(save_dialog)

    assert open_dialog.acceptMode() == QFileDialog.AcceptMode.AcceptOpen
    assert open_dialog.fileMode() == QFileDialog.FileMode.ExistingFile
    assert any("Tablesheet" in name_filter for name_filter in open_dialog.nameFilters())
    assert save_dialog.acceptMode() == QFileDialog.AcceptMode.AcceptSave
    assert save_dialog.defaultSuffix() == "log"


def test_message_dialogs_keep_copy_and_handle_empty_details(qtbot) -> None:
    warning = WarningDialog(title="Careful", text="Warning", detailed_text="")
    question = QuestionDialog(title="", text="", detailed_text="")
    qtbot.addWidget(warning)
    qtbot.addWidget(question)

    assert warning.icon() == QMessageBox.Icon.Warning
    assert warning.texts.title == "Careful"
    assert warning.text() == "Warning"
    assert question.icon() == QMessageBox.Icon.Question
    assert question.texts.title == ""
    assert question.text() == ""


def test_message_dialog_custom_icon_uses_configured_size(qtbot) -> None:
    dialog = QuestionDialog(
        icon=GenericIcons.DEVICE,
        title="Connect device",
        text="Do you want to connect?",
        detailed_text="Pair your phone first.",
    )
    qtbot.addWidget(dialog)

    expected_size = QSize(
        dialog_settings.MESSAGE_ICON_SIZE,
        dialog_settings.MESSAGE_ICON_SIZE,
    )
    assert dialog.iconPixmap().size() == expected_size


def test_message_dialog_custom_icon_offscreen_screenshot(
    qtbot, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    screenshot_dir = _dialog_screenshot_dir(tmp_path)

    dialogs = (
        (
            QuestionDialog(
                icon=GenericIcons.DEVICE,
                title="Connect device",
                text="Do you want to connect?",
                detailed_text="Pair your phone first.",
            ),
            "question_dialog_device.png",
        ),
        (
            WarningDialog(
                icon=GenericIcons.DEVICE,
                title="Device warning",
                text="Check your device settings.",
                detailed_text="Experimental software.",
            ),
            "warning_dialog_device.png",
        ),
    )

    for dialog, filename in dialogs:
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)

        pixmap = dialog.grab()
        assert pixmap.isNull() is False
        assert pixmap.width() > 0
        assert pixmap.height() > 0

        screenshot_path = screenshot_dir / filename
        assert pixmap.save(str(screenshot_path)) is True
        assert screenshot_path.exists()

        dialog.close()
