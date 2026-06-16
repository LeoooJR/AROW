"""Offscreen screenshot tests for input components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLineEdit

from gui.components.inputs import OTPInput, OTPType, SelectionField
from gui.tests.screenshot_helpers import capture_styled_widget_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_otp_input_ip_screenshot(qtbot, tmp_path) -> None:
    otp = OTPInput(
        None,
        otp_type=OTPType.IP,
        otp_length=4,
        max_length=[3, 3, 1, 1],
        echo_mode=QLineEdit.EchoMode.Normal,
    )
    for line_edit, value in zip(otp._otp_inputs, ["192", "168", "1", "1"], strict=True):
        line_edit.setText(value)
    capture_styled_widget_screenshot(
        qtbot,
        otp,
        tmp_path=tmp_path,
        filename="otp_input_ip.png",
        width=420,
        height=120,
    )


@pytest.mark.screenshot
def test_otp_line_edit_cell_screenshot(qtbot, tmp_path) -> None:
    otp = OTPInput(
        None, otp_type=OTPType.PORT, otp_length=5, max_length=[1, 1, 1, 1, 1]
    )
    line_edit = otp._otp_inputs[0]
    line_edit.setText("5")
    capture_styled_widget_screenshot(
        qtbot,
        line_edit,
        tmp_path=tmp_path,
        filename="otp_line_edit_cell.png",
        width=120,
        height=120,
    )


@pytest.mark.screenshot
def test_selection_field_screenshot(qtbot, tmp_path) -> None:
    field = SelectionField(None, "Choose one")
    field.addItem("Alpha")
    field.addItem("Beta")
    capture_styled_widget_screenshot(
        qtbot,
        field,
        tmp_path=tmp_path,
        filename="selection_field.png",
        width=320,
        height=120,
    )
