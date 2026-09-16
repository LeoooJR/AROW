"""Compact icon tool button component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolButton, QWidget

from gui.components.base.component import Component
from gui.components.buttons.button_settings import button_settings
from gui.constants.colors import Theme
from gui.constants.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.constants.settings import Settings


class ToolButton(QToolButton, Component):
    """Compact tool button with an optional theme-aware icon."""

    _icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None

    @dataclass(frozen=True)
    class Text:
        """Tooltip copy associated with the tool button."""

        tooltip: str | None = None

    @dataclass
    class UI:
        """Reserved for future explicit child references on the tool button."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
        tooltip: str | None = None,
        icon_size: int | None = None,
        theme_unresponsive: bool = False,
    ):
        """Create a compact icon button with optional tooltip.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
            tooltip: Hover tooltip string.
            icon_size: Optional square icon size override.
            theme_unresponsive: If True, the button will not change its theme when the application theme changes.
        """
        super().__init__(parent)

        self.setProperty("tool-button", True)
        self._theme_unresponsive = theme_unresponsive

        self.texts = ToolButton.Text(tooltip=tooltip)

        self._icon_size_px = icon_size or button_settings.TOOLBUTTON_ICON_SIZE
        self._icon = icon
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path(self._icon)))
            self.setIconSize(self._icon_size())
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if tooltip is not None:
                self.setToolTip(tooltip)

        self.ui = ToolButton.UI()

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setFixedHeight(button_settings.TOOLBUTTON_HEIGHT)
        self.setFixedWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the tool button icon for the active theme."""
        if self._theme_unresponsive:
            return
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path_for_theme(theme, self._icon)))

    def _icon_size(self) -> QSize:
        size = self._icon_size_px
        return QSize(size, size)

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None
    ):
        """Apply a new icon and optional size to the tool button.

        Args:
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
        """
        if icon is None:
            return

        self._icon = icon
        self.setIcon(QIcon(icon_qt_path(self._icon)))
        self.setIconSize(self._icon_size())
