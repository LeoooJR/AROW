"""Offscreen screenshot tests for dialog components."""

from __future__ import annotations

import pytest

from gui.components.dialogs import QuestionDialog, WarningDialog
from gui.icons import GenericIcons
from gui.tests.screenshot_helpers import capture_styled_top_level_screenshot

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.mark.screenshot
def test_question_dialog_device_icon_screenshot(qtbot, tmp_path) -> None:
    dialog = QuestionDialog(
        icon=GenericIcons.DEVICE,
        title="Connect device",
        text="Do you want to connect?",
        detailed_text="Pair your phone first.",
    )
    capture_styled_top_level_screenshot(
        qtbot,
        dialog,
        tmp_path=tmp_path,
        filename="question_dialog_device.png",
    )


@pytest.mark.screenshot
def test_warning_dialog_device_icon_screenshot(qtbot, tmp_path) -> None:
    dialog = WarningDialog(
        icon=GenericIcons.DEVICE,
        title="Device warning",
        text="Check your device settings.",
        detailed_text="Experimental software.",
    )
    capture_styled_top_level_screenshot(
        qtbot,
        dialog,
        tmp_path=tmp_path,
        filename="warning_dialog_device.png",
    )
