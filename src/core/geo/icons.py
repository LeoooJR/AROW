import base64
from enum import Enum
from pathlib import Path

import folium

from application_paths import APPLICATION_PATHS

# Correct MIME type for SVG to render it in the browser.
SVG_MIME = "image/svg+xml"


def create_custom_icon(icon_path: Path | str, **kwargs) -> folium.CustomIcon:
    """Create a folium CustomIcon with optional overrides."""
    path = Path(icon_path)
    if path.exists():
        svg_bytes = path.read_bytes()
        b64 = base64.b64encode(svg_bytes).decode("ascii")
        icon_image = f"data:{SVG_MIME};base64,{b64}"
    else:
        icon_image = str(icon_path)
    defaults = {
        "icon_image": icon_image,
        "icon_size": (48, 48),
        "icon_anchor": (24, 24),
        "popup_anchor": (0, -24),
    }
    defaults.update(kwargs)
    return folium.CustomIcon(**defaults)


class Icons(Enum):
    """
    Icons that are used to represent map elements.
    """

    BASE_URL = APPLICATION_PATHS.geo_icons_dir

    STATION = create_custom_icon(BASE_URL / "station.svg")
    MILESTONE = create_custom_icon(BASE_URL / "milestone.svg")
