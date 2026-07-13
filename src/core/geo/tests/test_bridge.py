"""Tests for the Folium-to-Qt map bridge JavaScript contract."""

from __future__ import annotations

from core.geo.bridge import (
    WEB_CHANNEL_INIT_JS,
    WEB_CHANNEL_SCRIPT_SRC,
    on_marker_clicked_js_code,
)


def test_web_channel_assets_bootstrap_qt_bridge() -> None:
    script_src = WEB_CHANNEL_SCRIPT_SRC.render()
    init_js = WEB_CHANNEL_INIT_JS.render()

    assert 'src="qrc:///qtwebchannel/qwebchannel.js"' in script_src
    assert "new QWebChannel(qt.webChannelTransport" in init_js
    assert "window.bridge = channel.objects.bridge" in init_js
    assert "setTimeout(initChannel, 50)" in init_js


def test_marker_click_script_sends_validatable_milestone_payload() -> None:
    script = on_marker_clicked_js_code("milestones_layer").render()

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
    script = on_marker_clicked_js_code("delayed_layer").render()

    assert "attachClick(tryCount + 1)" in script
    assert "tryCount < 80" in script
    assert "feature.geometry.coordinates[1]" in script
    assert "feature.geometry.coordinates[0]" in script
