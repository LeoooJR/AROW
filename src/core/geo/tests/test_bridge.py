"""Tests for the Folium-to-Qt map bridge JavaScript contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_bridge_module() -> ModuleType:
    """Load the standalone bridge module without triggering core.geo package imports."""
    bridge_path = Path(__file__).parents[1] / "bridge.py"
    spec = importlib.util.spec_from_file_location("_geo_bridge_under_test", bridge_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_web_channel_assets_bootstrap_qt_bridge() -> None:
    bridge = _load_bridge_module()

    script_src = bridge.WEB_CHANNEL_SCRIPT_SRC.render()
    init_js = bridge.WEB_CHANNEL_INIT_JS.render()

    assert 'src="qrc:///qtwebchannel/qwebchannel.js"' in script_src
    assert "new QWebChannel(qt.webChannelTransport" in init_js
    assert "window.bridge = channel.objects.bridge" in init_js
    assert "setTimeout(initChannel, 50)" in init_js


def test_marker_click_script_sends_validatable_milestone_payload() -> None:
    bridge = _load_bridge_module()

    script = bridge.on_marker_clicked_js_code("milestones_layer").render()

    assert 'var layerName = "milestones_layer"' in script
    assert 'layer.on("click", function(e)' in script
    assert "feature.properties.km" in script
    assert "feature.properties.code_ligne" in script
    assert "feature.properties.rg_troncon" in script
    assert "window.bridge.onMarkerClicked" in script
    assert "String(km)" in script
    assert "String(lineCode)" in script
    assert "Number(lineTroncon)" in script
    assert "latlng.lat" in script
    assert "latlng.lng" in script


def test_marker_click_script_retries_layer_lookup_and_uses_geometry_fallback() -> None:
    bridge = _load_bridge_module()

    script = bridge.on_marker_clicked_js_code("delayed_layer").render()

    assert "attachClick(tryCount + 1)" in script
    assert "tryCount < 80" in script
    assert "feature.geometry.coordinates[1]" in script
    assert "feature.geometry.coordinates[0]" in script
