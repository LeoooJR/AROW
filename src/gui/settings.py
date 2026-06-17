"""
Application-wide GUI settings.

Component- and block-specific settings live next to their owners in ``*_settings.py``
modules under ``gui/components`` and ``gui/blocks``.

When adding a new shared setting:
1. Decide scope: app-wide tokens belong here; owner-local values belong in the matching
   ``*_settings.py`` beside the component or block.
2. Add the field on the appropriate dataclass (``FontSettings``, ``SpacingSettings``, etc.).
3. Expose it through the ``Settings`` singleton when multiple modules need the same token.
4. Replace hardcoded literals in consumers with ``Settings.<GROUP>.<FIELD>`` (or the owner-local
   singleton when scope is local).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FontSettings:
    """Font-related settings used throughout the application.

    Primary face is bundled Inter, registered at startup via ``gui.fonts.register_bundled_fonts``
    (after ``QApplication`` exists). Stylesheet lists sensible system fallbacks if lookup fails.
    """

    FAMILY: str = "Inter"
    FAMILY_CSS: str = (
        '"Inter", "Helvetica Neue", "Helvetica", "Arial", "Liberation Sans", sans-serif'
    )
    MONO_FAMILY_CSS: str = (
        '"Geist Mono", "SF Mono", "IBM Plex Mono", "Menlo", "Consolas", monospace'
    )
    SIZE_DEFAULT: int = 16
    SIZE_SMALL: int = 8
    SIZE_HELPER: int = 14
    SIZE_LARGE: int = 20
    SIZE_TITLE: int = 24
    WEIGHT_NORMAL: int = 400
    WEIGHT_DEMIBOLD: int = 600


@dataclass(frozen=True)
class SpacingSettings:
    """Spacing and margin settings for layouts and components."""

    NONE: int = 0
    XS: int = 6
    SM: int = 8
    MD: int = 10
    LG: int = 12
    MARGIN_NONE: tuple = (0, 0, 0, 0)
    MARGIN_SMALL: tuple = (8, 6, 8, 6)
    MARGIN_MEDIUM: tuple = (10, 8, 10, 8)
    MARGIN_PANEL: tuple = (12, 12, 12, 12)
    MARGIN_PANEL_CONTENT: tuple = (12, 10, 12, 10)
    ICON_SPACING: int = 6


@dataclass(frozen=True)
class DimensionSettings:
    """Shared shell and layout dimension settings."""

    WINDOW_MIN_WIDTH: int = 1280
    WINDOW_MIN_HEIGHT: int = 720
    MIN_WIDTH_SMALL: int = 180
    MIN_WIDTH_MEDIUM: int = 200
    MIN_WIDTH_XLARGE: int = 300
    MIN_HEIGHT_MEDIUM: int = 200
    BASE_WIDTH: int = 260
    BASE_HEIGHT: int = 200


@dataclass(frozen=True)
class BorderRadiusSettings:
    """Border radius settings for rounded corners."""

    XS: int = 3
    SM: int = 6
    MD: int = 8
    LG: int = 10
    XL: int = 14


@dataclass(frozen=True)
class AnimationSettings:
    """Cross-cutting animation duration and timing settings."""

    PANEL_VISIBILITY_DURATION: int = 180
    ACTIVITY_IDLE_ESCALATION_STEP_MS: int = 10_000
    ACTIVITY_IDLE_ESCALATION_CAP_MS: int = 300_000


@dataclass(frozen=True)
class PanelSettings:
    """Shared panel chrome settings."""

    TITLE_PADDING_LEFT: int = 10
    TITLE_PADDING_TOP: int = 8
    TITLE_PADDING_RIGHT: int = 10
    TITLE_PADDING_BOTTOM: int = 8
    TITLE_ICON_SPACING: int = 8
    CONTENT_PADDING: int = 12
    SECTION_SPACING: int = 12
    UNBOUNDED_HEIGHT: int = 16777215


class Settings:
    """Centralized container for application-wide GUI settings."""

    FONT = FontSettings()
    SPACING = SpacingSettings()
    DIMENSION = DimensionSettings()
    BORDER_RADIUS = BorderRadiusSettings()
    ANIMATION = AnimationSettings()
    PANEL = PanelSettings()
