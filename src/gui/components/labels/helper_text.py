"""Helper text label component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.settings import Settings


class HelperText(QLabel, Component):

    @dataclass(frozen=True)
    class Text:
        """Helper or secondary caption text."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on helper text."""

        pass

    def __init__(self, parent: QWidget | None, text: str):
        """Create smaller helper-colored explanatory text.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Helper string.
        """

        super().__init__(text, parent)
        self.texts = HelperText.Text(label=text)

        self.setProperty("helper-text", True)
        self.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        self.ui = HelperText.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
