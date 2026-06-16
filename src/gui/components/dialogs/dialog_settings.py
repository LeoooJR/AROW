"""Dialog component settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DialogSettings:
    """Message dialog dimensions."""

    MESSAGE_ICON_SIZE: int = 64


dialog_settings = DialogSettings()
