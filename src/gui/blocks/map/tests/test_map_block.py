"""Tests for map block placeholder and helper behavior."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QAbstractAnimation

from gui.blocks.map import MapBlock
from gui.icons import GenericIcons

pytestmark = pytest.mark.usefixtures("qapp")


def test_map_block_updates_placeholder_text_and_icon(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    block.update_placeholder("Map is being loaded...", GenericIcons.MAP_PLACEHOLDER)

    assert block.ui.placeholder.ui.text.text() == "Map is being loaded..."
    assert block._placeholder_icon == GenericIcons.MAP_PLACEHOLDER


def test_map_block_placeholder_helper_animation_starts(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)

    block.play_placeholder_helper_animation()
    qtbot.wait(0)

    assert block._placeholder_helper_anim is not None
    assert (
        block._placeholder_helper_anim.state()
        == QAbstractAnimation.State.Running
    )


def test_map_block_placeholder_helper_animation_noops_without_svg(
    monkeypatch, qtbot
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    monkeypatch.setattr(block.ui.placeholder, "findChild", lambda *args: None)

    block.play_placeholder_helper_animation()

    assert block._placeholder_helper_anim is None
