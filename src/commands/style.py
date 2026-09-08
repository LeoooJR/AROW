"""Rich presentation primitives for AROW command-line interfaces."""

from typing import Final, Mapping

from rich.console import Console
from rich.theme import Theme
from typer import rich_utils

_PRIMARY_STYLE: Final[str] = "bold #ff6a00"
_MUTED_STYLE: Final[str] = "dim"
_SUCCESS_STYLE: Final[str] = "bold #3fa66e"
_ERROR_STYLE: Final[str] = "bold #d9544d"
_BORDER_STYLE: Final[str] = "bright_black"

# Terminal-owned foreground and background colors preserve light/dark theme parity.
# Brand and semantic accents mirror the canonical light palette in DESIGN.md.
AROW_THEME = Theme(
    {
        "arow.primary": _PRIMARY_STYLE,
        "arow.muted": _MUTED_STYLE,
        "arow.success": _SUCCESS_STYLE,
        "arow.error": _ERROR_STYLE,
        "arow.border": _BORDER_STYLE,
    }
)

# Typer creates its own Rich consoles, so its renderer needs explicit style values
# from the same semantic palette rather than the named theme entries above.
AROW_TYPER_STYLES: Final[Mapping[str, str]] = {
    "STYLE_ABORTED": _ERROR_STYLE,
    "STYLE_COMMANDS_PANEL_BORDER": _BORDER_STYLE,
    "STYLE_COMMANDS_TABLE_FIRST_COLUMN": _PRIMARY_STYLE,
    "STYLE_DEPRECATED": _ERROR_STYLE,
    "STYLE_ERRORS_PANEL_BORDER": _ERROR_STYLE,
    "STYLE_ERRORS_SUGGESTION": _MUTED_STYLE,
    "STYLE_HELPTEXT": _MUTED_STYLE,
    "STYLE_METAVAR": "bold",
    "STYLE_METAVAR_SEPARATOR": _MUTED_STYLE,
    "STYLE_NEGATIVE_OPTION": _PRIMARY_STYLE,
    "STYLE_NEGATIVE_SWITCH": _ERROR_STYLE,
    "STYLE_OPTION": _PRIMARY_STYLE,
    "STYLE_OPTIONS_PANEL_BORDER": _BORDER_STYLE,
    "STYLE_OPTION_DEFAULT": _MUTED_STYLE,
    "STYLE_OPTION_ENVVAR": _MUTED_STYLE,
    "STYLE_REQUIRED_LONG": _ERROR_STYLE,
    "STYLE_REQUIRED_SHORT": _ERROR_STYLE,
    "STYLE_SWITCH": _PRIMARY_STYLE,
    "STYLE_USAGE": _PRIMARY_STYLE,
    "STYLE_USAGE_COMMAND": "bold",
}


def configure_typer_styles() -> None:
    """Apply AROW's semantic palette to Typer's Rich renderer."""
    for attribute, style in AROW_TYPER_STYLES.items():
        setattr(rich_utils, attribute, style)


def create_console(*, stderr: bool = False) -> Console:
    """Create a Rich console configured with AROW's semantic CLI theme."""
    return Console(theme=AROW_THEME, stderr=stderr, highlight=False)


__all__ = [
    "AROW_THEME",
    "AROW_TYPER_STYLES",
    "configure_typer_styles",
    "create_console",
]
