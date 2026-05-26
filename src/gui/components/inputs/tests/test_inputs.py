"""Tests for input components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLineEdit

from gui.components.inputs import OTPInput, OTPType, SelectionField

pytestmark = pytest.mark.usefixtures("qapp")


def _set_otp_texts(input_widget: OTPInput, values: list[str]) -> None:
    for line_edit, value in zip(input_widget._otp_inputs, values, strict=True):
        line_edit.setText(value)


def test_otp_input_formats_valid_ip_and_tracks_invalid_indices(qtbot) -> None:
    otp = OTPInput(
        None,
        otp_type=OTPType.IP,
        otp_length=4,
        max_length=[3, 3, 1, 1],
        echo_mode=QLineEdit.EchoMode.Normal,
    )
    qtbot.addWidget(otp)

    _set_otp_texts(otp, ["192", "168", "1", "1"])

    assert otp.is_valid() is True
    assert otp.text() == "192.168.1.1"
    assert otp.get_invalid_index() == set()

    otp.clear()

    assert otp.is_valid() is False
    assert otp.get_invalid_index() == {0, 1, 2, 3}


def test_otp_input_rejects_mismatched_max_length() -> None:
    with pytest.raises(AssertionError, match="Max length list"):
        OTPInput(None, otp_length=4, max_length=[1, 1])


def test_selection_field_uses_placeholder_and_sorted_insert_policy(qtbot) -> None:
    field = SelectionField(None, "Choose one")
    qtbot.addWidget(field)

    field.addItem("Beta")
    field.addItem("Alpha")

    assert field.placeholderText() == "Choose one"
    assert field.isEditable() is False
    assert field.count() == 2
