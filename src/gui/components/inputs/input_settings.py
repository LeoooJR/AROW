"""Input component settings."""

from dataclasses import dataclass


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
class OTPSettings:
    """OTP input sizing."""

    INPUT_SIZE: int = 40


class InputSettings:
    """Input category settings container."""

    COMBOBOX = ComboBoxSettings()
    OTP = OTPSettings()


input_settings = InputSettings()
