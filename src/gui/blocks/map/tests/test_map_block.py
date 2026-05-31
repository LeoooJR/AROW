"""Tests for map block placeholder and helper behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation

from gui.blocks.map import MapBlock
from gui.icons import GenericIcons
from gui.signals import view_signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_map_block_updates_placeholder_text_and_icon(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    block.update_placeholder("Map is being loaded...", GenericIcons.MAP_PLACEHOLDER)

    assert block.placeholder.ui.text.text() == "Map is being loaded..."
    assert block._placeholder_icon == GenericIcons.MAP_PLACEHOLDER


def test_map_block_placeholder_helper_animation_starts(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.MapTabActivated.emit()
    qtbot.wait(0)

    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_placeholder_helper_animation_noops_without_svg(
    monkeypatch, qtbot
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()
    monkeypatch.setattr(block.placeholder, "findChild", lambda *args: None)

    view_signals.MapTabActivated.emit()

    assert block._placeholder_helper_anim is None


def test_map_block_connection_succeeded_updates_placeholder_and_animates(
    qtbot,
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.DeviceSelectionSucceeded.emit("d1", "Phone")
    qtbot.wait(0)

    assert block.placeholder.ui.text.text() == block.texts.loading_placeholder
    assert block._placeholder_icon == GenericIcons.MAP_PLACEHOLDER
    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_device_selection_failed_starts_helper_animation(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    view_signals.DeviceSelectionFailed.emit("d1")
    qtbot.wait(0)

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
