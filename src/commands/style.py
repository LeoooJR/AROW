"""Rich presentation primitives for AROW command-line interfaces."""

from rich.console import Console
from rich.theme import Theme

# Terminal-owned foreground and background colors preserve light/dark theme parity.
# Brand and semantic accents mirror the canonical light palette in DESIGN.md.
AROW_THEME = Theme(
    {
        "arow.primary": "bold #ff6a00",
        "arow.muted": "dim",
        "arow.success": "bold #3fa66e",
        "arow.error": "bold #d9544d",
        "arow.border": "bright_black",
    }
)


def create_console(*, stderr: bool = False) -> Console:
    """Create a Rich console configured with AROW's semantic CLI theme."""
    return Console(theme=AROW_THEME, stderr=stderr, highlight=False)


__all__ = ["AROW_THEME", "create_console"]
