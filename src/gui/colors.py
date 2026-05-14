"""
This file contains the colors used in the application.
Light and dark mode values are defined per color; dark mode is not yet tuned (same as light).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Theme = Literal["light", "dark"]

_APP_THEME: Theme = "light"


def get_current_theme() -> Theme:
    """Return the active UI theme (light or dark)."""
    return _APP_THEME


def set_current_theme(theme: Theme) -> None:
    """Set the active UI theme; intended to be driven from MainWindow palette updates."""
    global _APP_THEME
    _APP_THEME = theme


@dataclass(frozen=True)
class Color:
    """Single color with light and dark mode values."""

    name: str
    light_mode_value: str
    dark_mode_value: str

    def for_theme(self, theme: Theme) -> str:
        return self.light_mode_value if theme == "light" else self.dark_mode_value


class Colors(Enum):
    """Colors used in the application."""

    WHITE = Color("White", "#FFFFFF", "#FFFFFF")
    BLACK = Color("Black", "#000000", "#000000")
    COMPONENT = Color("Component", "#F5F5F5", "#F5F5F5")
    COMPONENT_HIGHLIGHT = Color("Component Highlight", "#E3E3E3", "#E3E3E3")
    PRIMARY = Color("Primary", "#FF6A00", "#FF6A00")
    PRIMARY_HOVER = Color("Primary Hover", "#FF8C33", "#FF8C33")
    SECONDARY = Color("Secondary", "#111111", "#111111")
    HIGHLIGHT = Color("Highlight", "#111111", "#111111")
    SUCCESS = Color("Success", "#00FF00", "#00FF00")
    ERROR = Color("Error", "#FF0000", "#FF0000")
    WARNING = Color("Warning", "#FFFF00", "#FFFF00")
    INFO = Color("Info", "#0000FF", "#0000FF")
    PLACEHOLDER = Color("Placeholder", "#D9D9D9", "#D9D9D9")
    PLACEHOLDER_TEXT = Color("Placeholder Text", "#9E9E9E", "#9E9E9E")
    TRANSPARENT = Color("Transparent", "transparent", "transparent")
    HELPER_TEXT = Color("Helper Text", "#808080", "#808080")
    LIGHT_DIVIDER = Color("Light Divider", "#E7E7E7", "#E7E7E7")
    LIGHT_DIVIDER_HIGHLIGHT = Color("Light Divider Highlight", "#D5D5D5", "#D5D5D5")
    PANEL_BORDER = Color("Panel Border", "#B0B0B0", "#B0B0B0")
    SOFT_RED = Color("Soft Red", "#E57373", "#C62828")
    SOFT_GREEN = Color("Soft Green", "#4CAF7D", "#2E7D57")


@dataclass(frozen=True)
class Palette:
    """Theme palette: one string value per color for a given theme."""

    WHITE: str
    BLACK: str
    COMPONENT: str
    COMPONENT_HIGHLIGHT: str
    PRIMARY: str
    PRIMARY_HOVER: str
    SECONDARY: str
    HIGHLIGHT: str
    SUCCESS: str
    ERROR: str
    WARNING: str
    INFO: str
    PLACEHOLDER: str
    PLACEHOLDER_TEXT: str
    TRANSPARENT: str
    HELPER_TEXT: str
    LIGHT_DIVIDER: str
    LIGHT_DIVIDER_HIGHLIGHT: str
    PANEL_BORDER: str
    SOFT_RED: str
    SOFT_GREEN: str


def get_palette(theme: Theme) -> Palette:
    """Return the color palette for the given theme (light or dark)."""
    return Palette(
        **{m.name: m.value.for_theme(theme) for m in Colors},
    )


def get_current_palette() -> Palette:
    """Return the color palette for the active theme."""
    return get_palette(get_current_theme())
