"""Folium bridge snippets for Qt WebChannel marker click handling."""

from branca.element import Element

# Loaded in the HTML <head>; must not be nested inside Folium's body <script> block.
WEB_CHANNEL_SCRIPT_SRC = Element(
    '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
)

# Plain JavaScript only — Folium wraps script children in a single outer <script> tag.
WEB_CHANNEL_INIT_JS = Element("""
(function() {
    function initChannel() {
        if (typeof QWebChannel === 'undefined' || typeof qt === 'undefined') {
            return setTimeout(initChannel, 50);
        }
        new QWebChannel(qt.webChannelTransport, function(channel) {
            window.bridge = channel.objects.bridge;
        });
    }
    initChannel();
})();
""")


def on_marker_clicked_js_code(js_object_name: str) -> Element:
    """Create inline JavaScript that wires milestone layer clicks to Qt bridge."""
    return Element(f"""
(function() {{
    var layerName = "{js_object_name}";
    function attachClick(tryCount) {{
        tryCount = tryCount || 0;
        var layer = window[layerName];
        if (!layer || typeof layer.on !== "function") {{
            if (tryCount < 80) {{
                return setTimeout(function() {{ attachClick(tryCount + 1); }}, 100);
            }}
            return;
        }}
        layer.on("click", function(e) {{
            if (!window.bridge || !window.bridge.onMarkerClicked) {{
                return;
            }}
            var hitLayer = e.layer || e.target;
            var feature = hitLayer && hitLayer.feature;
            if (!feature || !feature.properties) {{
                return;
            }}
            var km = feature.properties.km;
            if (km == null) {{
                return;
            }}
            var lineCode = feature.properties.code_ligne;
            if (lineCode == null) {{
                return;
            }}
            var lineTroncon = feature.properties.rg_troncon;
            if (lineTroncon == null) {{
                return;
            }}
            var latlng = e.latlng;
            if (!latlng && feature.geometry && feature.geometry.coordinates) {{
                latlng = {{
                    lat: feature.geometry.coordinates[1],
                    lng: feature.geometry.coordinates[0],
                }};
            }}
            if (!latlng) {{
                return;
            }}
            window.bridge.onMarkerClicked(
                String(km),
                String(lineCode),
                Number(lineTroncon),
                latlng.lat,
                latlng.lng
            );
        }});
    }}
    attachClick();
}})();
""")
