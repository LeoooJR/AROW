"""Map blocks."""

from gui.blocks.map.device_required_placeholder import DeviceRequiredMapPlaceholder
from gui.blocks.map.map import Canvas, Coordinates, Legend, Location, Map, MapBlock
from gui.blocks.map.map_loading_placeholder import MapLoadingPlaceholder
from gui.blocks.map.map_render_failed_placeholder import MapRenderFailedPlaceholder

__all__ = [
    "Canvas",
    "Coordinates",
    "DeviceRequiredMapPlaceholder",
    "Legend",
    "Location",
    "Map",
    "MapBlock",
    "MapLoadingPlaceholder",
    "MapRenderFailedPlaceholder",
]
