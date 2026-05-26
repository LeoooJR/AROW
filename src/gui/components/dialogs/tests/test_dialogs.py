"""Tests for dialog components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from gui.components.dialogs import (
    FileOpenDialog,
    FileSaveDialog,
    QuestionDialog,
    WarningDialog,
)

pytestmark = pytest.mark.usefixtures("qapp")


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
