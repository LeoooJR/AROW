"""Top bar block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TopBarSettings:
    """Header chrome dimensions and palette animation timing."""

    HEADER_HEIGHT: int = 60
    PALETTE_THUMB_SIZE: int = 28
    APP_NAME_WIDTH: int = 100
    APP_NAME_HEIGHT: int = 30
    PALETTE_SWITCH_DURATION: int = 200


top_bar_settings = TopBarSettings()
