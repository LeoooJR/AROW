"""
Tests for the shared file display widget.

Headless CI: use ``QT_QPA_PLATFORM=offscreen`` if the platform plugin fails.
"""

from __future__ import annotations

import pytest

from gui.components import File

pytestmark = pytest.mark.usefixtures("qapp")


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
