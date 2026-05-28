"""
This file contains all application-wide settings used in the GUI.
Settings are organized into logical groups for easy access and maintenance.
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

    # Layout spacing
    NONE: int = 0
    XS: int = 6
    SM: int = 8
    MD: int = 10
    LG: int = 12

    # Layout margins (left, top, right, bottom)
    MARGIN_NONE: tuple = (0, 0, 0, 0)
    MARGIN_SMALL: tuple = (8, 6, 8, 6)
    MARGIN_MEDIUM: tuple = (10, 8, 10, 8)
    MARGIN_PANEL: tuple = (12, 12, 12, 12)
    MARGIN_PANEL_CONTENT: tuple = (12, 10, 12, 10)
    MARGIN_TOAST: tuple = (20, 16, 20, 16)

    # Icon spacing
    ICON_SPACING: int = 6


@dataclass(frozen=True)
class DimensionSettings:
    """Dimension settings for widgets and components."""

    # Header
    HEADER_HEIGHT: int = 60

    # Buttons
    BUTTON_HEIGHT: int = 30
    TOOLBUTTON_HEIGHT: int = 30
    TOOLBUTTON_ICON_SIZE: int = 18
    TOOLBUTTON_PROMINENT_ICON_SIZE: int = 22
    PALETTE_THUMB_SIZE: int = 28

    # Logo and branding
    LOGO_SIZE: int = 90
    # Welcome tab: logo sized to balance with app-name SVG + tagline in hero
    WELCOME_LOGO_SIZE: int = 200
    APP_NAME_WIDTH: int = 100
    APP_NAME_HEIGHT: int = 30

    # Canvas
    CANVAS_SIZE: int = 1000

    # Window
    WINDOW_MIN_WIDTH: int = 1280
    WINDOW_MIN_HEIGHT: int = 720

    # Minimum dimensions
    MIN_WIDTH_SMALL: int = 180
    MIN_WIDTH_MEDIUM: int = 200
    MIN_WIDTH_LARGE: int = 260
    MIN_WIDTH_XLARGE: int = 300
    MIN_HEIGHT_SMALL: int = 150
    MIN_HEIGHT_MEDIUM: int = 200

    # Base sizes
    BASE_WIDTH: int = 260
    BASE_HEIGHT: int = 200

    # Location widget
    LOCATION_WIDGET_MIN_WIDTH: int = 200
    LOCATION_WIDGET_MAX_HEIGHT: int = 50

    # Toast
    TOAST_MIN_WIDTH: int = 300
    TOAST_MAX_WIDTH: int = 400
    TOAST_OFFSET: int = 20

    # Progress bar
    PROGRESSBAR_HEIGHT: int = 20

    # Condition indicator (e.g. host identity status)
    CONDITION_INDICATOR_SIZE: int = 10

    # Welcome walkthrough: large card-style connection rows
    WELCOME_WALKTHROUGH_CARD_MIN_HEIGHT: int = 80
    WELCOME_WALKTHROUGH_CARD_PADDING_H: int = 22
    WELCOME_WALKTHROUGH_CARD_PADDING_V: int = 20
    WELCOME_WALKTHROUGH_CARD_LEAD_ICON_SIZE: int = 40

    # Authentification card
    AUTENTHIFICATION_CARD_MIN_WIDTH: int = 380
    AUTENTHIFICATION_CARD_MAX_WIDTH: int = 520
    OTP_INPUT_SIZE: int = 40


@dataclass(frozen=True)
class BorderRadiusSettings:
    """Border radius settings for rounded corners."""

    XS: int = 3
    SM: int = 6
    MD: int = 8
    LG: int = 10
    XL: int = 14


@dataclass(frozen=True)
class SVGSettings:
    """SVG icon size calculation settings."""

    # Multipliers for SVG size based on font size
    MULTIPLIER_SMALL: float = 1.6  # For font_size < 20
    MULTIPLIER_LARGE: float = 1.4  # For font_size >= 20
    MULTIPLIER_PANEL_TITLE: float = 1.3  # For panel title icons


@dataclass(frozen=True)
class AnimationSettings:
    """Animation duration and timing settings."""

    TOAST_FADE_IN_DURATION: int = 200  # milliseconds
    TOAST_DISPLAY_DURATION: int = 3000  # milliseconds
    PANEL_VISIBILITY_DURATION: int = 180  # milliseconds for panel collapse/expand
    SIMULATION_STATE_TRANSITION_DURATION: int = (
        220  # milliseconds for state label crossfade
    )
    PALETTE_SWITCH_DURATION: int = 200  # milliseconds for palette thumb slide
    PLACEHOLDER_HELPER_DURATION: int = (
        600  # milliseconds for map placeholder phone-icon pulse (connect reminder)
    )
    PLACEHOLDER_HELPER_ITERATION: int = 3  # milliseconds to delay the helper animation
    INDICATOR_PULSE_DURATION: int = (
        1000  # milliseconds per pulse cycle (warning/error states)
    )
    ATTENTION_HIGHLIGHT_DURATION: int = (
        2500  # total duration of pulse highlight effects
    )
    ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS: int = (
        1000  # one full fade-in/fade-out cycle (ms)
    )
    ATTENTION_HIGHLIGHT_UPDATE_MS: int = (
        40  # timer interval for smooth level updates (~25 fps)
    )
    # ActivityTracker: each idle timeout without input lengthens the next single-shot poll.
    ACTIVITY_IDLE_ESCALATION_STEP_MS: int = 10_000
    ACTIVITY_IDLE_ESCALATION_CAP_MS: int = 300_000


@dataclass(frozen=True)
class ShadowSettings:
    """Shadow effect settings."""

    BLUR_RADIUS: int = 12
    X_OFFSET: int = 0
    Y_OFFSET: int = 4
    COLOR_RGBA: tuple = (0, 0, 0, 30)  # (r, g, b, alpha)


@dataclass(frozen=True)
class PanelSettings:
    """Panel-specific settings."""

    # Panel title padding
    TITLE_PADDING_LEFT: int = 10
    TITLE_PADDING_TOP: int = 8
    TITLE_PADDING_RIGHT: int = 10
    TITLE_PADDING_BOTTOM: int = 8
    TITLE_ICON_SPACING: int = 8

    # Panel content padding
    CONTENT_PADDING: int = 12

    # Section spacing
    SECTION_SPACING: int = 12

    # Panel unbounded height
    UNBOUNDED_HEIGHT: int = 16777215


@dataclass(frozen=True)
class WelcomeSettings:
    """Welcome tab (IDE-style) layout: hero, max-width content row, section cards."""

    CONTENT_MAX_WIDTH: int = 880
    EXPANDED_CONTENT_MAX_WIDTH: int = 1420
    CARD_PADDING_LEFT: int = 20
    CARD_PADDING_TOP: int = 18
    CARD_PADDING_RIGHT: int = 20
    CARD_PADDING_BOTTOM: int = 18
    HERO_BOTTOM_SPACING: int = 24
    HERO_ELEMENT_SPACING: int = 10
    APP_NAME_SVG_HEIGHT: int = 28


@dataclass(frozen=True)
class ComboBoxSettings:
    """ComboBox/SelectionField settings."""

    MIN_WIDTH: int = 260
    MIN_HEIGHT: int = 40
    PADDING_LEFT: int = 30
    PADDING_RIGHT: int = 30
    PADDING_TOP: int = 8
    PADDING_BOTTOM: int = 8
    DROPDOWN_WIDTH: int = 15
    ITEM_VIEW_MIN_WIDTH: int = 300


@dataclass(frozen=True)
class ListSettings:
    """List widget settings."""

    MIN_WIDTH: int = 180
    MIN_HEIGHT: int = 150
    BASE_WIDTH: int = 260
    BASE_HEIGHT: int = 200
    ITEM_PADDING_VERTICAL: int = 10
    ITEM_PADDING_HORIZONTAL: int = 12
    ITEM_MARGIN_VERTICAL: int = 2
    ITEM_MIN_HEIGHT: int = 24
    DEVICE_ITEM_ROW_PADDING_V: int = 8
    DEVICE_ITEM_ROW_PADDING_H: int = 8
    DEVICE_ITEM_ROW_TITLE_SUBTITLE_SPACING: int = 6
    DEVICE_ITEM_CENTER_PADDING_V: int = 0
    DEVICE_ITEM_ROW_ICON_GAP: int = 12
    DEVICE_ITEM_ROW_NAME_BADGE_GAP: int = 10
    DEVICE_ITEM_ROW_RIGHT_GAP: int = 10
    DEVICE_ITEM_ROW_MIN_HEIGHT: int = 90
    DEVICE_ITEM_ROW_COMPACT_PREFERRED_WIDTH: int = 250
    DEVICE_ITEM_ROW_EXTENDED_PREFERRED_WIDTH: int = 420
    DEVICE_ITEM_ICON_FRAME: int = 44
    ACTIVITY_ITEM_ROW_PADDING_V: int = 8
    ACTIVITY_ITEM_ROW_PADDING_H: int = 8
    ACTIVITY_ITEM_ROW_ICON_FRAME: int = 30
    ACTIVITY_ITEM_ICON_SIZE: int = 16
    ACTIVITY_ITEM_ROW_ICON_GAP: int = 8
    ACTIVITY_ITEM_ROW_MIN_HEIGHT: int = 58
    ACTIVITY_ITEM_DETAIL_PADDING: int = 8
    ACTIVITY_ITEM_PREFERRED_WIDTH: int = 360
    SCROLLBAR_WIDTH: int = 12
    SCROLLBAR_HANDLE_MIN_HEIGHT: int = 30
    SCROLLBAR_HANDLE_MIN_WIDTH: int = 30
    SCROLLBAR_MARGIN: int = 4
    SCROLLBAR_HANDLE_MARGIN: int = 2
    # How often relative “last communication” labels refresh (list + device state).
    LAST_COMMUNICATION_REFRESH_MS: int = 60_000


@dataclass(frozen=True)
class PlaceHolderSettings:
    """Placeholder widget settings."""

    MIN_WIDTH: int = 180
    MIN_HEIGHT: int = 150
    PADDING: int = 10
    MARGIN: int = 10
    ICON_SIZE: int = 80  # Size of optional SVG icon above text
    SPACING: int = 12  # Vertical spacing between icon and text


@dataclass(frozen=True)
class MapSettings:
    """Map panel specific settings."""

    LEGEND_PADDING_LEFT: int = 12
    LEGEND_PADDING_TOP: int = 10
    LEGEND_PADDING_RIGHT: int = 12
    LEGEND_PADDING_BOTTOM: int = 10
    LEGEND_SPACING: int = 12
    COORDINATES_SPACING: int = 10
    MAP_SPACING: int = 12


@dataclass(frozen=True)
class LocationSettings:
    """Location widget specific settings."""

    WIDGET_MIN_WIDTH: int = 200
    WIDGET_MAX_HEIGHT: int = 50
    WIDGET_PADDING_LEFT: int = 12
    WIDGET_PADDING_TOP: int = 10
    WIDGET_PADDING_RIGHT: int = 12
    WIDGET_PADDING_BOTTOM: int = 10
    WIDGET_SPACING: int = 8
    COORDINATE_SPACING: int = 12
    LABEL_FONT_SIZE: int = 8
    TARGET_PADDING_LEFT: int = 14
    TARGET_PADDING_TOP: int = 12
    TARGET_PADDING_RIGHT: int = 14
    TARGET_PADDING_BOTTOM: int = 12
    TARGET_BLOCK_SPACING: int = 16
    METADATA_GRID_SPACING: int = 8
    METADATA_GRID_HORIZONTAL_SPACING: int = 18
    METADATA_GRID_VERTICAL_SPACING: int = 16
    METADATA_KEY_VALUE_SPACING: int = 6


@dataclass(frozen=True)
class HostPanelSettings:
    """Host panel specific settings (visual rhythm and compact metadata rows)."""

    WRAPPER_MARGIN: tuple = (4, 4, 4, 4)
    SECTION_SPACING: int = 8
    ROW_SPACING: int = 6
    KEY_VALUE_SPACING: int = 10


class Settings:
    """
    Centralized settings container for all application-wide settings.
    Access settings through this class for consistency.
    """

    FONT = FontSettings()
    SPACING = SpacingSettings()
    DIMENSION = DimensionSettings()
    BORDER_RADIUS = BorderRadiusSettings()
    SVG = SVGSettings()
    ANIMATION = AnimationSettings()
    SHADOW = ShadowSettings()
    PANEL = PanelSettings()
    WELCOME = WelcomeSettings()
    COMBOBOX = ComboBoxSettings()
    LIST = ListSettings()
    PLACEHOLDER = PlaceHolderSettings()
    MAP = MapSettings()
    LOCATION = LocationSettings()
    HOST_PANEL = HostPanelSettings()
