"""Start-screen block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StartSettings:
    """Start-screen section card padding."""

    CARD_PADDING_LEFT: int = 20
    CARD_PADDING_TOP: int = 18
    CARD_PADDING_RIGHT: int = 20
    CARD_PADDING_BOTTOM: int = 18


start_settings = StartSettings()
