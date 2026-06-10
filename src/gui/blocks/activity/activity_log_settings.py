"""Activity log block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActivityLogSettings:
    """Activity log row, icon, and detail sizing."""

    ITEM_ROW_PADDING_V: int = 8
    ITEM_ROW_PADDING_H: int = 8
    ITEM_ROW_ICON_FRAME: int = 30
    ITEM_ICON_SIZE: int = 16
    ITEM_ROW_ICON_GAP: int = 8
    ITEM_ROW_MIN_HEIGHT: int = 58
    ITEM_DETAIL_PADDING: int = 8
    ITEM_PREFERRED_WIDTH: int = 360


activity_log_settings = ActivityLogSettings()
