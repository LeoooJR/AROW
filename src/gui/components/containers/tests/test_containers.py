"""Tests for container components."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout

from gui.components.containers import AuthentificationCard, GroupBox, PlaceHolder
from gui.icons import GenericIcons, icon_qt_path
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_group_box_adds_widgets_to_supplied_layout(qtbot) -> None:
    child = QLabel("Inside")
    group = GroupBox(None, layout=QVBoxLayout(), widgets=[child], title="Group")
    qtbot.addWidget(group)

    assert group.title() == "Group"
    assert group.layout().indexOf(child) == 0
    assert group.property("group-box") is True


def test_placeholder_updates_text_icon_and_supports_missing_icon(qtbot) -> None:
    placeholder = PlaceHolder(None, "Empty", icon=GenericIcons.DEVICE_PLACEHOLDER)
    no_icon_placeholder = PlaceHolder(None, "No icon")
    qtbot.addWidget(placeholder)
    qtbot.addWidget(no_icon_placeholder)

    placeholder.set_text("Still empty")
    placeholder.set_icon(GenericIcons.MAP_PLACEHOLDER)
    no_icon_placeholder.apply_theme_icons("dark")

    assert placeholder.ui.text.text() == "Still empty"
    assert placeholder.ui.svg.isHidden() is False
    assert no_icon_placeholder.ui.svg.isHidden() is True


def test_authentification_card_emits_confirm_for_valid_inputs(qtbot) -> None:
    card = AuthentificationCard(
        None,
        title="Pair",
        icon_path=icon_qt_path(GenericIcons.DEVICE),
        description="Connect",
    )
    qtbot.addWidget(card)

    for input_widget, values in (
        (card.ui.ip_otp_input, ["192", "168", "1", "1"]),
        (card.ui.port_otp_input, ["5", "5", "5", "5", "5"]),
        (card.ui.association_code_otp_input, ["1", "2", "3", "4", "5", "6"]),
    ):
        for line_edit, value in zip(input_widget._otp_inputs, values, strict=True):
            line_edit.setText(value)

    with qtbot.waitSignal(view_signals.AuthentificationConfirmed) as signal:
        card.ui.confirm_button.click()

    assert signal.args == ["192.168.1.1", "55555", "123456"]


def test_authentification_card_handles_missing_optional_copy_and_invalid_submit(
    qtbot,
) -> None:
    card = AuthentificationCard(None)
    qtbot.addWidget(card)

    card.ui.confirm_button.click()
    qtbot.wait(0)

    assert card.ui.title.isHidden() is True
    assert card.ui.description.isHidden() is True
    assert card.ui.icon.isHidden() is True
    assert card._invalid_targets
