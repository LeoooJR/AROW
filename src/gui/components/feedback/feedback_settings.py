"""Feedback component settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToastSettings:
    """Toast sizing, margin, and fade timing."""

    MIN_WIDTH: int = 300
    MAX_WIDTH: int = 400
    OFFSET: int = 20
    MARGIN: tuple = (20, 16, 20, 16)
    FADE_IN_DURATION: int = 200


@dataclass(frozen=True)
class ShadowSettings:
    """Shadow effect settings."""

    BLUR_RADIUS: int = 12
    X_OFFSET: int = 0
    Y_OFFSET: int = 4
    COLOR_RGBA: tuple = (0, 0, 0, 30)


class FeedbackSettings:
    """Feedback category settings container."""

    TOAST = ToastSettings()
    SHADOW = ShadowSettings()


feedback_settings = FeedbackSettings()
