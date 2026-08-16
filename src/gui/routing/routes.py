"""Named application page routes."""

from enum import StrEnum


class PageRoute(StrEnum):
    """Stable identifiers for pages displayed in the main workspace."""

    WELCOME = "welcome"
    MAP = "map"
    DEVICE = "device"
