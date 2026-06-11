"""Card block settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CardSettings:
    """Identity and bridge card layout rhythm."""

    WRAPPER_MARGIN: tuple = (4, 4, 4, 4)
    ROW_SPACING: int = 6
    KEY_VALUE_SPACING: int = 10


card_settings = CardSettings()
