"""Primary action button component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from gui.components.base.component import Component
from gui.components.buttons.button_settings import button_settings
from gui.components.media import get_svg_size
from gui.constants.colors import Theme
from gui.constants.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.constants.settings import Settings


class Button(QPushButton, Component):
    """Styled primary action button with optional theme-aware icon."""

    _icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None

    @dataclass(frozen=True)
    class Text:
        """Primary action label for the button."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the button."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        text: str,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
        theme_unresponsive: bool = False,
    ):
        """Create a styled primary button with optional icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Button label text.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown before the label.
            theme_unresponsive: If True, the button will not change its theme when the application theme changes.
        """
        self._theme_unresponsive = theme_unresponsive

        if icon is not None:
            super().__init__(QIcon(icon_qt_path(icon)), text, parent)
            self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
            self._icon = icon
        else:
            super().__init__(text, parent)
            self._icon = None

        self.setProperty("button", True)

        self.texts = Button.Text(label=text)

        self.ui = Button.UI()

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setFixedHeight(button_settings.BUTTON_HEIGHT)
        # Set minimum width based on content, but allow horizontal expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the button icon for the active theme."""
        if self._theme_unresponsive:
            return
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path_for_theme(theme, self._icon)))
