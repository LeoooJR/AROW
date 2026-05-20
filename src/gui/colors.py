"""
This file contains the colors used in the application.
Light and dark mode values follow the AROW design system in DESIGN.md.
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

    CANVAS = Color("Canvas", "#FFFFFF", "#10100F")
    SURFACE = Color("Surface", "#F7F7F6", "#171716")
    SURFACE_ELEVATED = Color("Surface Elevated", "#FFFFFF", "#20201E")
    SURFACE_MUTED = Color("Surface Muted", "#EFEFED", "#2A2A27")
    BORDER_SUBTLE = Color("Border Subtle", "#E7E7E2", "#363632")
    BORDER_STRONG = Color("Border Strong", "#BDBDB7", "#55554E")
    TEXT_PRIMARY = Color("Text Primary", "#0A0A0A", "#FAF9F6")
    TEXT_MUTED = Color("Text Muted", "#7A7A74", "#A7A49D")
    PRIMARY = Color("Primary", "#FF6A00", "#FF7A1A")
    PRIMARY_HOVER = Color("Primary Hover", "#FF8C33", "#FF9A4D")
    PRIMARY_SOFT = Color("Primary Soft", "#FFF0E6", "rgba(255, 106, 0, 0.18)")
    PRIMARY_BORDER = Color("Primary Border", "#FFD3B8", "rgba(255, 106, 0, 0.34)")
    SUCCESS = Color("Success", "#3FA66E", "#55C083")
    SUCCESS_SOFT = Color("Success Soft", "#EAF7F0", "rgba(85, 192, 131, 0.16)")
    SUCCESS_BORDER = Color("Success Border", "#BFE6D0", "rgba(85, 192, 131, 0.32)")
    ERROR = Color("Error", "#D9544D", "#F07167")
    WARNING = Color("Warning", "#D98A24", "#E6A04A")
    INFO = Color("Info", "#2F6FED", "#7AA2FF")
    WHITE = Color("White", "#FFFFFF", "#FAF9F6")
    BLACK = Color("Black", "#0A0A0A", "#FAF9F6")
    COMPONENT = Color("Component", "#F7F7F6", "#171716")
    COMPONENT_HIGHLIGHT = Color("Component Highlight", "#EFEFED", "#2A2A27")
    SECONDARY = Color("Secondary", "#0A0A0A", "#FAF9F6")
    HIGHLIGHT = Color("Highlight", "#BDBDB7", "#55554E")
    PLACEHOLDER = Color("Placeholder", "#EFEFED", "#2A2A27")
    PLACEHOLDER_TEXT = Color("Placeholder Text", "#7A7A74", "#A7A49D")
    TRANSPARENT = Color("Transparent", "transparent", "transparent")
    HELPER_TEXT = Color("Helper Text", "#7A7A74", "#A7A49D")
    LIGHT_DIVIDER = Color("Light Divider", "#E7E7E2", "#363632")
    LIGHT_DIVIDER_HIGHLIGHT = Color("Light Divider Highlight", "#BDBDB7", "#55554E")
    PANEL_BORDER = Color("Panel Border", "#BDBDB7", "#55554E")
    PANEL_TITLE_BACKGROUND = Color(
        "Panel Title Background",
        "rgba(247, 247, 246, 0.72)",
        "rgba(23, 23, 22, 0.72)",
    )
    SOFT_RED = Color("Soft Red", "#D9544D", "#F07167")
    SOFT_GREEN = Color("Soft Green", "#3FA66E", "#55C083")


@dataclass(frozen=True)
class Palette:
    """Theme palette: one string value per color for a given theme."""

    CANVAS: str
    SURFACE: str
    SURFACE_ELEVATED: str
    SURFACE_MUTED: str
    BORDER_SUBTLE: str
    BORDER_STRONG: str
    TEXT_PRIMARY: str
    TEXT_MUTED: str
    PRIMARY_SOFT: str
    PRIMARY_BORDER: str
    SUCCESS_SOFT: str
    SUCCESS_BORDER: str
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
    PANEL_TITLE_BACKGROUND: str
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
