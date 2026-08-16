"""Styled combo box selection field component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QWidget

from gui.components.base.component import Component
from gui.components.inputs.input_settings import input_settings
from gui.constants.colors import Theme
from gui.constants.settings import Settings


class SelectionField(QComboBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Placeholder string for the non-editable combo field."""

        placeholder: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the selection field."""

        pass

    def __init__(self, parent: QWidget | None, placeholder: str):
        """Configure a styled combo box with placeholder text.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            placeholder: Shown when no item is selected meaningfully.
        """

        super().__init__(parent)

        self.texts = SelectionField.Text(placeholder=placeholder)

        self.setProperty("selection-field", True)
        self.setEditable(False)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setInsertPolicy(QComboBox.InsertPolicy.InsertAlphabetically)
        self.setMinimumWidth(input_settings.COMBOBOX.MIN_WIDTH)
        self.setMinimumHeight(input_settings.COMBOBOX.MIN_HEIGHT)
        self.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )

        self.setPlaceholderText(placeholder)
        self.setCurrentIndex(0)

        self.ui = SelectionField.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
