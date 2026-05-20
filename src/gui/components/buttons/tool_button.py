"""Compact icon tool button component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolButton, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.svg import get_svg_size


class ToolButton(QToolButton, Component):

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
    ):
        """Create a compact icon button with optional tooltip.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
            tooltip: Hover tooltip string.
        """
        super().__init__(parent)

        self.setProperty("tool-button", True)

        self.texts = ToolButton.Text(tooltip=tooltip)

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path(self._icon)))
            self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if tooltip is not None:
                self.setToolTip(tooltip)

        self.ui = ToolButton.UI()

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setFixedHeight(Settings.DIMENSION.TOOLBUTTON_HEIGHT)
        self.setFixedWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path_for_theme(theme, self._icon)))

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None
    ):
        """Apply a new icon and optional size to the tool button.

        Args:
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
        """
        if icon is None:
            return

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon
        self.setIcon(QIcon(icon_qt_path(self._icon)))
        self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
