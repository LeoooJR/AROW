"""Start-screen block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StartSettings:
    """Start-screen section card padding."""

    CARD_PADDING_LEFT: int = 20
    CARD_PADDING_TOP: int = 18
    CARD_PADDING_RIGHT: int = 20
    CARD_PADDING_BOTTOM: int = 18
    RECENT_EMPTY_PLACEHOLDER_MIN_HEIGHT: int = 188
    RECENT_EMPTY_GLYPH_WIDTH: int = 142
    RECENT_EMPTY_GLYPH_HEIGHT: int = 92
    RECENT_EMPTY_FILE_ICON_SIZE: int = 34
    RECENT_EMPTY_CONTENT_MAX_WIDTH: int = 360


start_settings = StartSettings()
