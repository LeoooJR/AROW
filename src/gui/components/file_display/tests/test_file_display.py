"""Tests for the file display component."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gui.components.file_display import File
from gui.signals import signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_file_display_updates_name_and_type(qtbot) -> None:
    file_widget = File(None, "activity.log", "log", file_save=True)
    qtbot.addWidget(file_widget)

    assert file_widget._file_name_label.text() == "activity.log"
    assert file_widget._file_type_label.text() == "LOG"
    assert hasattr(file_widget, "_save_as_button")

    file_widget.set_file_display("latest.txt", "txt")

    assert file_widget._file_name == "latest.txt"
    assert file_widget._file_type_label.text() == "TXT"
    assert file_widget._file_date_label is None


def test_file_display_renders_optional_date_text(qtbot) -> None:
    file_widget = File(
        None,
        "kilometer-marker_128450.log",
        "log",
        date_text="Last opened 2026-05-26",
    )
    qtbot.addWidget(file_widget)

    assert file_widget._file_type_label.text() == "LOG"
    assert file_widget._file_date_label is not None
    assert file_widget._file_date_label.text() == "Last opened 2026-05-26"


def test_file_display_updates_optional_date_text(qtbot) -> None:
    file_widget = File(None, "activity.log", "log")
    qtbot.addWidget(file_widget)

    file_widget.set_file_display(
        "inspection-context.kml", "kml", "Last opened 2026-05-21"
    )

    assert file_widget._file_name == "inspection-context.kml"
    assert file_widget._file_type_label.text() == "KML"
    assert file_widget._file_date_label is not None
    assert file_widget._file_date_label.text() == "Last opened 2026-05-21"

    file_widget.set_file_display("inspection-context.kml", "kml")

    assert file_widget._file_date_label is not None
    assert file_widget._file_date_label.isHidden() is True


def test_file_display_without_save_button_and_empty_name_refreshes_safely(
    qtbot,
) -> None:
    file_widget = File(None, "", "", file_save=False)
    qtbot.addWidget(file_widget)

    file_widget.refresh_display()

    assert not hasattr(file_widget, "_save_as_button")
    assert file_widget._file_name_label.text() == ""
    assert file_widget._file_type_label.text() == ""


def test_file_display_save_as_emits_activity_log_file_update_requested(
    monkeypatch, qtbot, log_records
) -> None:
    file_widget = File(None, "activity.log", "log", file_save=True)
    qtbot.addWidget(file_widget)

    dialog = MagicMock()
    dialog.exec.return_value = True
    dialog.selectedFiles.return_value = ["/tmp/custom_activity.log"]
    monkeypatch.setattr(
        "gui.components.file_display.file_display.FileSaveDialog",
        lambda parent: dialog,
    )

    emitted: list[str] = []
    signals.ACTIVITY_LOG.ActivityLogFileUpdateRequested.connect(emitted.append)

    file_widget._on_save_as_button_clicked()

    assert emitted == ["/tmp/custom_activity.log"]
    record = log_records[-1]
    assert record["level"].name == "INFO"
    assert record["message"] == "Activity log file selected"
    assert record["extra"]["path"] == "/tmp/custom_activity.log"


def test_file_display_name_survives_narrow_then_wide_resize(qtbot) -> None:
    widget = File(
        None,
        file_name="especially_serious_8017.log",
        file_type="log",
        file_save=True,
    )
    qtbot.addWidget(widget)
    widget.resize(120, 72)
    widget.show()
    qtbot.wait(0)
    widget.refresh_display()
    qtbot.wait(0)

    narrow_text = widget._file_name_label.text()

    widget.resize(320, 72)
    widget.refresh_display()
    qtbot.wait(0)

    assert narrow_text.strip()
    assert widget._file_name_label.text().strip()


def test_file_display_refresh_while_hidden_restores_full_name(qtbot) -> None:
    widget = File(None, file_name="hidden-layout-route.geojson", file_type="geojson")
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(0)
    widget._file_name_label.setText("")

    widget.hide()
    widget.refresh_display()
    qtbot.wait(0)

    assert widget._file_name_label.text() == "hidden-layout-route.geojson"


def test_set_file_display_updates_labels_and_keeps_name_visible(qtbot) -> None:
    widget = File(None, file_name="old.log", file_type="log")
    qtbot.addWidget(widget)
    widget.resize(260, 72)
    widget.show()
    qtbot.wait(0)

    widget.set_file_display("fresh-simulation-output.txt", "txt")
    qtbot.wait(0)

    assert widget._file_name_label.text().strip()
    assert widget._file_type_label.text() == "TXT"
