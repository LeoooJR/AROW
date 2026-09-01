"""Container component settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceHolderSettings:
    """Placeholder widget settings."""

    MIN_WIDTH: int = 180
    MIN_HEIGHT: int = 150
    PADDING: int = 10
    MARGIN: int = 10
    ICON_SIZE: int = 80
    SPACING: int = 12


@dataclass(frozen=True)
class AuthentificationCardSettings:
    """Authentification card dimensions."""

    MIN_WIDTH: int = 380
    MAX_WIDTH: int = 520


@dataclass(frozen=True)
class ShutdownCardSettings:
    """Managed-shutdown card dimensions."""

    MIN_WIDTH: int = 380
    MAX_WIDTH: int = 520
    STATUS_ICON_SIZE: int = 48
    STATUS_GLYPH_SIZE: int = 20


@dataclass(frozen=True)
class AttentionHighlightSettings:
    """Shared pulse-highlight animation timing for attention drawers."""

    DURATION: int = 2500
    PULSE_CYCLE_MS: int = 1000
    UPDATE_MS: int = 40


class ContainerSettings:
    """Container category settings container."""

    PLACEHOLDER = PlaceHolderSettings()
    AUTHENTIFICATION_CARD = AuthentificationCardSettings()
    SHUTDOWN_CARD = ShutdownCardSettings()
    ATTENTION_HIGHLIGHT = AttentionHighlightSettings()


container_settings = ContainerSettings()
