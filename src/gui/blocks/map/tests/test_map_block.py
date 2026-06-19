"""Tests for map block placeholder and helper behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWebEngineCore import QWebEngineSettings

from gui.blocks.map.map import (
    _INVALIDATE_LEAFLET_MAPS_JS,
    Canvas,
    MapBlock,
)
from gui.signals import signals

pytestmark = pytest.mark.usefixtures("qapp")


def test_canvas_configures_local_folium_support_and_refreshes_leaflet_on_load(
    monkeypatch, qtbot
) -> None:
    canvas = Canvas()
    qtbot.addWidget(canvas)
    web_settings = canvas.settings()
    page = MagicMock()
    monkeypatch.setattr(canvas, "page", lambda: page)

    assert web_settings.testAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled)
    assert web_settings.testAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls
    )
    assert web_settings.testAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls
    )

    canvas._on_load_finished(True)
    page.runJavaScript.assert_called_once_with(_INVALIDATE_LEAFLET_MAPS_JS)

    canvas._on_load_finished(False)
    page.runJavaScript.assert_called_once()


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

    with qtbot.waitSignal(signals.UI.DisplayLeftPanelsRequested):
        block.ui.device_required_placeholder.ui.open_device_list_button.click()


def test_map_block_placeholder_helper_animation_starts(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    signals.UI.MapTabActivated.emit()
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

    signals.UI.MapTabActivated.emit()

    assert calls == [None]


def test_map_block_connection_succeeded_updates_placeholder_and_animates(
    qtbot,
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    signals.DEVICE.DeviceSelectionSucceeded.emit("sim-1", "d1", "Phone")
    qtbot.wait(0)

    assert block.placeholder.currentWidget() is block.ui.map_loading_placeholder
    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_load_map_html_shows_canvas_and_loads_local_file(
    monkeypatch, qtbot, tmp_path: Path
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    html_path = tmp_path / "sim-1.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    load = MagicMock()
    monkeypatch.setattr(block.ui.canvas, "load", load)
    show_map_canvas = MagicMock()
    monkeypatch.setattr(block, "show_map_canvas", show_map_canvas)
    monkeypatch.setattr(block, "_map_html_path", lambda simulation_id: html_path)

    block._load_map_html("sim-1")
    qtbot.waitUntil(lambda: load.call_count == 1, timeout=1000)

    show_map_canvas.assert_called_once_with()
    load.assert_called_once()
    loaded_url = load.call_args.args[0]
    assert loaded_url.toLocalFile() == str(html_path.resolve())


def test_map_block_load_map_html_noops_when_rendered_file_is_missing(
    monkeypatch, qtbot, tmp_path: Path
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    missing_path = tmp_path / "missing.html"
    load = MagicMock()
    monkeypatch.setattr(block.ui.canvas, "load", load)
    show_map_canvas = MagicMock()
    monkeypatch.setattr(block, "show_map_canvas", show_map_canvas)
    monkeypatch.setattr(block, "_map_html_path", lambda simulation_id: missing_path)

    block._load_map_html("sim-1")

    show_map_canvas.assert_not_called()
    load.assert_not_called()


def test_map_block_device_selection_success_requests_render_only(
    monkeypatch, qtbot
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()
    events: list[tuple[str, str]] = []
    load_calls: list[str] = []

    def capture_render(simulation_id: str) -> None:
        events.append(("render", simulation_id))

    def capture_load(simulation_id: str) -> None:
        load_calls.append(simulation_id)

    monkeypatch.setattr(block, "_load_map_html", capture_load)

    signals.UI.RenderMapRequested.connect(capture_render)
    try:
        block._on_device_selection_succeeded("sim-1", "d1", "Phone")
    finally:
        signals.UI.RenderMapRequested.disconnect(capture_render)

    assert block.placeholder.currentWidget() is block.ui.map_loading_placeholder
    assert events == [("render", "sim-1")]
    assert load_calls == []


def test_map_block_map_rendered_slot_loads_html_from_path(
    monkeypatch, qtbot, tmp_path: Path
) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    html_path = tmp_path / "sim-1.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    load = MagicMock()
    monkeypatch.setattr(block.ui.canvas, "load", load)
    show_map_canvas = MagicMock()
    monkeypatch.setattr(block, "show_map_canvas", show_map_canvas)

    block._on_map_rendered("sim-1", str(html_path))
    qtbot.waitUntil(lambda: load.call_count == 1, timeout=1000)

    show_map_canvas.assert_called_once_with()
    load.assert_called_once()
    loaded_url = load.call_args.args[0]
    assert loaded_url.toLocalFile() == str(html_path.resolve())


def test_map_block_map_render_failed_resets_placeholder(monkeypatch, qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()
    block.show_map_loading_placeholder()
    load = MagicMock()
    monkeypatch.setattr(block.ui.canvas, "load", load)

    block._on_map_render_failed("sim-1", "render failed")

    assert block.placeholder.currentWidget() is block.ui.device_required_placeholder
    assert block.ui.placeholder.isVisible()
    assert not block.ui.canvas.isVisible()
    load.assert_not_called()


def test_map_block_device_selection_failed_starts_helper_animation(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    signals.DEVICE.DeviceSelectionFailed.emit("d1", "Phone")
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

    signals.DEVICE.RemoveActiveDeviceSucceeded.emit("d1")
    qtbot.wait(0)

    assert block.placeholder.currentWidget() is block.ui.device_required_placeholder
    assert block._placeholder_helper_anim is not None
    assert block._placeholder_helper_anim.state() == QAbstractAnimation.State.Running


def test_map_block_authentification_failed_starts_helper_animation(qtbot) -> None:
    block = MapBlock()
    qtbot.addWidget(block)
    block.show()

    signals.DEVICE.AuthentificationFailed.emit("err", 1, "detail")
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

    signals.UI.MapTabActivated.emit()
    qtbot.wait(0)

    assert block._placeholder_helper_anim is None
