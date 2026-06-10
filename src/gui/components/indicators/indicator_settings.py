"""Indicator component settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IndicatorSettings:
    """Progress bar and condition-indicator sizing and pulse timing."""

    PROGRESSBAR_HEIGHT: int = 20
    CONDITION_INDICATOR_SIZE: int = 10
    PULSE_DURATION: int = 1000


indicator_settings = IndicatorSettings()
