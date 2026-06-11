"""Generic list widget settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ListSettings:
    """List widget and scrollbar settings."""

    MIN_WIDTH: int = 200
    MIN_HEIGHT: int = 200
    BASE_WIDTH: int = 260
    BASE_HEIGHT: int = 200
    ITEM_PADDING_VERTICAL: int = 10
    ITEM_PADDING_HORIZONTAL: int = 12
    ITEM_MARGIN_VERTICAL: int = 2
    ITEM_MIN_HEIGHT: int = 24
    SCROLLBAR_WIDTH: int = 12
    SCROLLBAR_HANDLE_MIN_HEIGHT: int = 30
    SCROLLBAR_HANDLE_MIN_WIDTH: int = 30
    SCROLLBAR_MARGIN: int = 4
    SCROLLBAR_HANDLE_MARGIN: int = 2


list_settings = ListSettings()
