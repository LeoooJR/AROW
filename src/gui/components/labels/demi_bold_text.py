"""Demi-bold text label component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

from gui.components.base.component import Component
from gui.constants.colors import Theme
from gui.constants.settings import Settings


class DemiBoldText(QLabel, Component):

    @dataclass(frozen=True)
    class Text:
        """Demi-bold label content."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on demi-bold text."""

        pass

    def __init__(self, parent: QWidget | None, text: str):
        """Create a demi-bold emphasis label.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Label string.
        """
        super().__init__(text, parent)
        self.texts = DemiBoldText.Text(label=text)

        self.setProperty("demi-bold-text", True)
        self.setFont(
            QFont(
                Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.DemiBold
            )
        )
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        self.ui = DemiBoldText.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
