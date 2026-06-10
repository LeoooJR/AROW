"""Device block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceSettings:
    """Device list rows, empty state, refresh, and highlight settings."""

    ITEM_ROW_PADDING_V: int = 8
    ITEM_ROW_PADDING_H: int = 8
    ITEM_ROW_TITLE_SUBTITLE_SPACING: int = 6
    ITEM_CENTER_PADDING_V: int = 0
    ITEM_ROW_ICON_GAP: int = 12
    ITEM_ROW_NAME_BADGE_GAP: int = 10
    ITEM_ROW_RIGHT_GAP: int = 10
    ITEM_ROW_MIN_HEIGHT: int = 90
    ITEM_ROW_COMPACT_PREFERRED_WIDTH: int = 250
    ITEM_ROW_EXTENDED_PREFERRED_WIDTH: int = 420
    ITEM_ICON_FRAME: int = 44
    EMPTY_STATE_WIDTH: int = 250
    EMPTY_STATE_ACTION_WIDTH: int = 190
    EMPTY_STATE_GLYPH_TITLE_SPACING: int = 16
    REFRESH_MS: int = 60_000
    NEW_DEVICE_BADGE_DURATION_SECONDS: int = 5 * 60
    ATTENTION_HIGHLIGHT_DURATION: int = 2500
    ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS: int = 1000
    ATTENTION_HIGHLIGHT_UPDATE_MS: int = 40


device_settings = DeviceSettings()
