"""Warning and question message dialog components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget

from gui.components.base.component import Component
from gui.components.dialogs.dialog_settings import dialog_settings
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme


def _message_dialog_icon_pixmap(qt_path: str) -> QPixmap:
    """Return a message-box icon pixmap scaled to the configured dialog size."""
    size = dialog_settings.MESSAGE_ICON_SIZE
    return QIcon(qt_path).pixmap(QSize(size, size))


class WarningDialog(QMessageBox, Component):
    """Theme-aware warning dialog with confirmation actions."""

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

    def __init__(
        self,
        parent: QWidget = None,
        icon: GenericIcons | None = None,
        title=str,
        text=str,
        detailed_text=str,
    ):
        """Show a warning message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            icon: Icon to display in the dialog.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self._icon = icon
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
        if icon is not None:
            self.setIconPixmap(_message_dialog_icon_pixmap(icon_qt_path(icon)))
        else:
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
        """Refresh the custom warning icon for the active theme."""
        if self._icon is not None:
            self.setIconPixmap(
                _message_dialog_icon_pixmap(icon_qt_path_for_theme(theme, self._icon))
            )


class QuestionDialog(QMessageBox, Component):
    """Theme-aware question dialog with confirmation actions."""

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

    def __init__(
        self,
        parent: QWidget = None,
        icon: GenericIcons | None = None,
        title=str,
        text=str,
        detailed_text=str,
    ):
        """Show a question message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            icon: Icon to display in the dialog.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self._icon = icon
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
        if icon is not None:
            self.setIconPixmap(_message_dialog_icon_pixmap(icon_qt_path(icon)))
        else:
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
        """Refresh the custom question icon for the active theme."""
        if self._icon is not None:
            self.setIconPixmap(
                _message_dialog_icon_pixmap(icon_qt_path_for_theme(theme, self._icon))
            )
