"""Tests for label components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from gui.components.labels import DemiBoldText, HelperText, LeadingIconLabel
from gui.constants.icons import GenericIcons

pytestmark = pytest.mark.usefixtures("qapp")


def test_helper_and_demi_bold_labels_keep_text_and_properties(qtbot) -> None:
    helper = HelperText(None, "Secondary")
    title = DemiBoldText(None, "Important")
    qtbot.addWidget(helper)
    qtbot.addWidget(title)

    assert helper.text() == "Secondary"
    assert helper.property("helper-text") is True
    assert title.text() == "Important"
    assert title.property("demi-bold-text") is True


def test_leading_icon_label_accepts_string_and_custom_label(qtbot) -> None:
    label = LeadingIconLabel(None, GenericIcons.INFO, "Status")
    replacement = QLabel("External")
    qtbot.addWidget(label)

    assert label.texts.text == "Status"
    assert label.ui.text.text() == "Status"

    label.set_text(replacement)

    assert label.texts.text is None
    assert label.ui.text is replacement
    assert replacement.parent() is label


def test_leading_icon_label_rejects_invalid_icon_and_ignores_empty_text(qtbot) -> None:
    label = LeadingIconLabel(None, GenericIcons.INFO, "Status")
    qtbot.addWidget(label)

    with pytest.raises(ValueError):
        LeadingIconLabel(None, None, "Broken")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        label.set_icon("not-an-icon")  # type: ignore[arg-type]

    label.set_text(None)

    assert label.ui.text.text() == "Status"
