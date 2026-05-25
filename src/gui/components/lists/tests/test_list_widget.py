"""Tests for the styled list widget."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QListWidgetItem

from gui.components.lists import List

pytestmark = pytest.mark.usefixtures("qapp")


def test_list_adds_and_iterates_string_and_item_rows(qtbot) -> None:
    item = QListWidgetItem("Concrete")
    list_widget = List(None, items=["First", item])
    qtbot.addWidget(list_widget)

    list_widget.add_items(["Second", QListWidgetItem("Third")])

    assert list_widget.is_empty() is False
    assert [row.text() for row in list_widget.iter_items()] == [
        "First",
        "Concrete",
        "Second",
        "Third",
    ]


def test_list_reports_empty_and_rejects_unsupported_item_type(qtbot) -> None:
    list_widget = List(None, items=[])
    qtbot.addWidget(list_widget)

    assert list_widget.is_empty() is True

    with pytest.raises(TypeError):
        list_widget.add_items([object()])
