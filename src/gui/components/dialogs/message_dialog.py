"""Warning and question message dialog components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from gui.colors import Theme
from gui.components.base.component import Component


class WarningDialog(QMessageBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Primary, detailed, and informative strings for the warning box."""

        title: str = ""
        text: str = ""
        detailed_text: str = ""
        informative_text: Final[str] = (
            "This software is for experimental purposes. Use at your own risk."
        )

    @dataclass
    class UI:
        """Reserved for future explicit child references on the warning dialog."""

        pass

    def __init__(self, parent: QWidget = None, title=str, text=str, detailed_text=str):
        """Show a warning message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self.texts = WarningDialog.Text(
            title=title,
            text=text,
            detailed_text=detailed_text,
        )
        self.ui = WarningDialog.UI()

        self.setWindowTitle(self.texts.title)
        self.setText(self.texts.text)
        self.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        self.setDetailedText(self.texts.detailed_text)
        self.setInformativeText(self.texts.informative_text)
        self.setIcon(QMessageBox.Icon.Warning)

        for label in self.findChildren(QLabel):
            if label.text() == self.informativeText():
                label.setProperty("messagebox-informative-text", True)
            elif label.text() == self.detailedText():
                label.setProperty("messagebox-detailed-text", True)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class QuestionDialog(QMessageBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Primary, detailed, and informative strings for the question box."""

        title: str = ""
        text: str = ""
        detailed_text: str = ""
        informative_text: Final[str] = (
            "This software is for experimental purposes. Use at your own risk."
        )

    @dataclass
    class UI:
        """Reserved for future explicit child references on the question dialog."""

        pass

    def __init__(self, parent: QWidget = None, title=str, text=str, detailed_text=str):
        """Show a question message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self.texts = QuestionDialog.Text(
            title=title,
            text=text,
            detailed_text=detailed_text,
        )
        self.ui = QuestionDialog.UI()

        self.setWindowTitle(self.texts.title)
        self.setText(self.texts.text)
        self.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        self.setDetailedText(self.texts.detailed_text)
        self.setInformativeText(self.texts.informative_text)
        self.setIcon(QMessageBox.Icon.Question)

        for label in self.findChildren(QLabel):
            if label.text() == self.informativeText():
                label.setProperty("messagebox-informative-text", True)
            elif label.text() == self.detailedText():
                label.setProperty("messagebox-detailed-text", True)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
