"""
Application color tokens: theme-aware values and palette helpers.

Light and dark mode values follow the AROW design system in ``DESIGN.md``.

When adding a new color:
1. Add a ``Colors`` enum member with light and dark ``Color`` values aligned to ``DESIGN.md``.
2. Add the matching field on ``Palette`` so ``get_palette`` can resolve it.
3. Reference the token from ``src/gui/constants/stylesheet.py`` or painter code via ``get_palette`` /
   ``get_current_palette`` (not one-off hex literals in widgets).
4. Extend theme or painter tests under ``src/gui/tests/`` when the token drives painted UI.
"""

from __future__ import annotations

import importlib
import platform
import re
import shutil
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal

from PySide6.QtGui import QColor

_CSS_RGB_PATTERN = re.compile(
    r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)$",
    re.IGNORECASE,
)
_THEME_LOOKUP_TIMEOUT_SECONDS: Final[float] = 0.5
_MACOS_INTERFACE_STYLE_ARGS: Final[tuple[str, ...]] = (
    "read",
    "-g",
    "AppleInterfaceStyle",
)
_LINUX_GNOME_COLOR_SCHEME_ARGS: Final[tuple[str, ...]] = (
    "get",
    "org.gnome.desktop.interface",
    "color-scheme",
)
_WINDOWS_APPS_USE_LIGHT_THEME_VALUE: Final[str] = "AppsUseLightTheme"
_WINDOWS_PERSONALIZE_REGISTRY_PATH: Final[str] = (
    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
)

Theme = Literal["light", "dark"]

_APP_THEME: Theme = "light"


def _run_fixed_theme_subprocess(
    executable_name: str,
    args: tuple[str, ...],
) -> str | None:
    """Run a fixed-argument OS theme probe when the executable is on PATH.

    Uses the resolved executable path (never a shell) and returns stdout on
    success, or ``None`` when the tool is missing or the subprocess fails.
    """
    executable_path = shutil.which(executable_name)
    if executable_path is None:
        return None
    try:
        completed = subprocess.run(  # nosec B603
            [executable_path, *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=_THEME_LOOKUP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _theme_from_macos() -> Theme:
    """Return the macOS appearance, defaulting to light when unset."""
    output = _run_fixed_theme_subprocess("defaults", _MACOS_INTERFACE_STYLE_ARGS)
    if output is None:
        return "light"
    return "dark" if output.lower() == "dark" else "light"


def _theme_from_windows() -> Theme:
    """Return the Windows app appearance from the user personalization registry."""
    if sys.platform != "win32":
        return "light"

    winreg = importlib.import_module("winreg")
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _WINDOWS_PERSONALIZE_REGISTRY_PATH,
        ) as key:
            value, _ = winreg.QueryValueEx(key, _WINDOWS_APPS_USE_LIGHT_THEME_VALUE)
    except OSError:
        return "light"

    try:
        apps_use_light_theme = int(value)
    except (TypeError, ValueError):
        return "light"
    if apps_use_light_theme not in (0, 1):
        return "light"
    return "light" if apps_use_light_theme == 1 else "dark"


def _theme_from_linux() -> Theme:
    """Return the Linux desktop color scheme when exposed through GNOME settings."""
    output = _run_fixed_theme_subprocess("gsettings", _LINUX_GNOME_COLOR_SCHEME_ARGS)
    if output is None:
        return "light"
    normalized = output.strip("'\"").lower()
    if "dark" in normalized:
        return "dark"
    return "light"


def get_system_theme() -> Theme:
    """Return the current operating system theme for known desktop platforms."""
    system_name = platform.system().lower()
    try:
        if system_name == "darwin":
            return _theme_from_macos()
        if system_name == "windows":
            return _theme_from_windows()
        if system_name == "linux":
            return _theme_from_linux()
    except (
        FileNotFoundError,
        OSError,
        subprocess.SubprocessError,
        TimeoutError,
        ImportError,
        ValueError,
    ):
        return "light"
    return "light"


def initialize_app_theme_from_system() -> Theme:
    """Set and return the active UI theme from the operating system preference."""
    global _APP_THEME
    _APP_THEME = get_system_theme()
    return _APP_THEME


initialize_app_theme_from_system()


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
        """Return the color value associated with ``theme``."""
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
    ERROR_SOFT = Color("Error Soft", "#FCEBEA", "rgba(240, 113, 103, 0.14)")
    ERROR_BORDER = Color("Error Border", "#F2C3C0", "rgba(240, 113, 103, 0.34)")
    WARNING = Color("Warning", "#D98A24", "#E6A04A")
    WARNING_SOFT = Color("Warning Soft", "#FFF5E7", "rgba(230, 160, 74, 0.14)")
    WARNING_BORDER = Color("Warning Border", "#F1D5AC", "rgba(230, 160, 74, 0.34)")
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
    ERROR_SOFT: str
    ERROR_BORDER: str
    WARNING: str
    WARNING_SOFT: str
    WARNING_BORDER: str
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


def qcolor_from_css(value: str) -> QColor:
    """Build a QColor from a palette/CSS color string.

    Qt stylesheets accept CSS ``rgb(...)`` / ``rgba(...)`` syntax, but
    ``QColor(str)`` does not. This helper keeps palette tokens unchanged while
    letting painter code render semi-transparent fills and strokes correctly.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("Palette color value must not be empty.")

    match = _CSS_RGB_PATTERN.match(normalized)
    if match is not None:
        red, green, blue, alpha = match.groups()
        qt_alpha = 255 if alpha is None else round(float(alpha) * 255)
        color = QColor(int(red), int(green), int(blue), qt_alpha)
        if not color.isValid():
            raise ValueError(f"Invalid CSS color components in {value!r}.")
        return color

    color = QColor(normalized)
    if not color.isValid():
        raise ValueError(f"Unsupported palette color value for QPainter: {value!r}.")
    return color
