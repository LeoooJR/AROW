"""Welcome tab settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WelcomeSettings:
    """Welcome tab expanded workspace width."""

    EXPANDED_CONTENT_MAX_WIDTH: int = 1420


welcome_settings = WelcomeSettings()
