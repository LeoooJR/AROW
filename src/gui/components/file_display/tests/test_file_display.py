"""Tests for the file display component."""

from __future__ import annotations

import pytest

from gui.components.file_display import File

pytestmark = pytest.mark.usefixtures("qapp")


def test_file_display_updates_name_and_type(qtbot) -> None:
    file_widget = File(None, "simulation.log", "log", file_save=True)
    qtbot.addWidget(file_widget)

    assert file_widget._file_name_label.text() == "simulation.log"
    assert file_widget._file_type_label.text() == "LOG"
    assert hasattr(file_widget, "_save_as_button")

    file_widget.set_file_display("latest.txt", "txt")

    assert file_widget._file_name == "latest.txt"
    assert file_widget._file_type_label.text() == "TXT"


def test_file_display_without_save_button_and_empty_name_refreshes_safely(
    qtbot,
) -> None:
    file_widget = File(None, "", "", file_save=False)
    qtbot.addWidget(file_widget)

    file_widget.refresh_display()

    assert not hasattr(file_widget, "_save_as_button")
    assert file_widget._file_name_label.text() == ""
    assert file_widget._file_type_label.text() == ""
