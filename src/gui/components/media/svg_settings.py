"""SVG media component settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SVGSettings:
    """SVG icon size calculation settings."""

    MULTIPLIER_SMALL: float = 1.6
    MULTIPLIER_LARGE: float = 1.4


svg_settings = SVGSettings()
