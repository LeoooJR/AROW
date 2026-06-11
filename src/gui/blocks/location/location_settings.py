"""Location block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LocationSettings:
    """Milestone target block padding and metadata grid settings."""

    TARGET_PADDING_LEFT: int = 14
    TARGET_PADDING_TOP: int = 12
    TARGET_PADDING_RIGHT: int = 14
    TARGET_PADDING_BOTTOM: int = 12
    TARGET_BLOCK_SPACING: int = 16
    METADATA_GRID_HORIZONTAL_SPACING: int = 18
    METADATA_GRID_VERTICAL_SPACING: int = 16
    METADATA_KEY_VALUE_SPACING: int = 6


location_settings = LocationSettings()
