"""Button and tool-button dimension settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ButtonSettings:
    """Button, tool-button, and walkthrough-button dimensions."""

    BUTTON_HEIGHT: int = 30
    TOOLBUTTON_HEIGHT: int = 30
    TOOLBUTTON_ICON_SIZE: int = 18
    TOOLBUTTON_PROMINENT_ICON_SIZE: int = 22
    WELCOME_WALKTHROUGH_CARD_MIN_HEIGHT: int = 80
    WELCOME_WALKTHROUGH_CARD_PADDING_H: int = 22
    WELCOME_WALKTHROUGH_CARD_PADDING_V: int = 20


button_settings = ButtonSettings()
