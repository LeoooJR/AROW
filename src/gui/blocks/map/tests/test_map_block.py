"""Tests for map block placeholder and helper behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation

from gui.blocks.map import MapBlock
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_map_block_shows_loading_placeholder(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    block.show_map_loading_placeholder()

    assert block.placeholder.currentWidget() is block.ui.map_loading_placeholder


def test_map_block_initial_state_shows_device_required_placeholder(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    placeholder = block.ui.device_required_placeholder

    assert block.placeholder.currentWidget() is placeholder
    assert placeholder.layout().itemAt(1).widget() is placeholder.ui.glyph
    assert placeholder.layout().itemAt(2).widget() is placeholder.ui.title_label
    assert placeholder.layout().itemAt(3).widget() is placeholder.ui.description_label
    assert (
        placeholder.layout().itemAt(4).widget()
        is placeholder.ui.open_device_list_button
    )
    assert placeholder.ui.title_label.text() == "Choose a device to open the map"
    assert (
        placeholder.ui.description_label.text()
        == "The map becomes available after an Android device is linked and selected."
    )
    assert placeholder.ui.open_device_list_button.text().strip() == "Open device list"


def test_map_block_device_required_placeholder_resizes_without_overlap(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    placeholder = block.ui.device_required_placeholder

    for width in (900, 680, 560, 460):
        block.resize(width, 560)
        qtbot.wait(0)

        assert not placeholder.ui.glyph.geometry().intersects(
            placeholder.ui.title_label.geometry()
        )
        assert not placeholder.ui.glyph.geometry().intersects(
            placeholder.ui.description_label.geometry()
        )
        assert not placeholder.ui.glyph.geometry().intersects(
            placeholder.ui.open_device_list_button.geometry()
        )


def test_map_block_open_device_list_cta_shows_left_panels(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    with qtbot.waitSignal(view_signals.LeftPanelsVisibilityRequested) as signal:
        block.ui.device_required_placeholder.ui.open_device_list_button.click()

    assert signal.args == [True]


def test_map_block_placeholder_helper_animation_starts(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.MapTabActivated.emit()
    qtbot.wait(0)

    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_placeholder_helper_animation_is_delegated(
    monkeypatch, qtbot
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()
    calls = []

    def fake_play_helper_animation(previous_animation):
        calls.append(previous_animation)
        return previous_animation

    monkeypatch.setattr(
        block.ui.device_required_placeholder,
        "play_helper_animation",
        fake_play_helper_animation,
    )

    view_signals.MapTabActivated.emit()

    assert calls == [None]


def test_map_block_connection_succeeded_updates_placeholder_and_animates(
    qtbot,
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.DeviceSelectionSucceeded.emit("d1", "Phone")
    qtbot.wait(0)

    assert block.placeholder.currentWidget() is block.ui.map_loading_placeholder
    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_device_selection_failed_starts_helper_animation(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.DeviceSelectionFailed.emit("d1", "Phone")
    qtbot.wait(0)

    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_active_device_removed_resets_placeholder_and_animates(
    qtbot,
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    block.show_map_loading_placeholder()

    view_signals.RemoveActiveDeviceSucceeded.emit("d1")
    qtbot.wait(0)

    assert block.placeholder.currentWidget() is block.ui.device_required_placeholder
    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_authentification_failed_starts_helper_animation(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.AuthentificationFailed.emit("err", 1, "detail")
    qtbot.wait(0)

    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_placeholder_helper_animation_noops_when_canvas_visible(
    qtbot,
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()
    block.canvas.setVisible(True)
    block.placeholder.setVisible(False)

    view_signals.MapTabActivated.emit()
    qtbot.wait(0)

    assert block._placeholder_helper_anim is None
