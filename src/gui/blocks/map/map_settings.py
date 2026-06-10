"""Map block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class MapSettings:
    """Map canvas, legend, coordinates, and placeholder animation settings."""

    CANVAS_SIZE: int = 1000
    LEGEND_PADDING_LEFT: int = 12
    LEGEND_PADDING_TOP: int = 10
    LEGEND_PADDING_RIGHT: int = 12
    LEGEND_PADDING_BOTTOM: int = 10
    LEGEND_SPACING: int = 12
    COORDINATES_SPACING: int = 10
    MAP_SPACING: int = 12
    COORDINATE_WIDGET_MIN_WIDTH: int = 200
    COORDINATE_WIDGET_MAX_HEIGHT: int = 50
    COORDINATE_WIDGET_PADDING_LEFT: int = 12
    COORDINATE_WIDGET_PADDING_TOP: int = 10
    COORDINATE_WIDGET_PADDING_RIGHT: int = 12
    COORDINATE_WIDGET_PADDING_BOTTOM: int = 10
    COORDINATE_WIDGET_SPACING: int = 8
    COORDINATE_SPACING: int = 12
    LABEL_FONT_SIZE: int = 8
    MIN_WIDTH_LARGE: int = 260
    MIN_HEIGHT_SMALL: int = 150
    SIMULATION_STATE_TRANSITION_DURATION: int = 220
    PLACEHOLDER_HELPER_DURATION: int = 600
    PLACEHOLDER_HELPER_ITERATION: int = 3


map_settings = MapSettings()
