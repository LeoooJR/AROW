"""File open and save dialog components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QDir
from PySide6.QtWidgets import QFileDialog, QWidget

from gui.colors import Theme
from gui.components.base.component import Component


class FileOpenDialog(QFileDialog, Component):

    @dataclass(frozen=True)
    class Text:
        """Default window title and name filter for spreadsheet open."""

        window_title: Final[str] = "Open a file"
        name_filter: Final[str] = "Tablesheet files (*.xlsx, *.xls, *.csv)"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the open dialog."""

        pass

    def __init__(self, parent: QWidget = None):
        """Configure a read-only open dialog for tabular files.

        Args:
            parent: Optional parent window for modality placement.
        """

        super().__init__(parent)
        self.texts = FileOpenDialog.Text()
        self.ui = FileOpenDialog.UI()

        self.setWindowTitle(self.texts.window_title)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.setNameFilter(self.texts.name_filter)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setFilter(QDir.Filter.Files | QDir.Filter.Readable)
        self.setOptions(
            QFileDialog.Option.ReadOnly | QFileDialog.Option.DontUseCustomDirectoryIcons
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class FileSaveDialog(QFileDialog, Component):

    @dataclass(frozen=True)
    class Text:
        """Default window title, filter, and suffix for log save."""

        window_title: Final[str] = "Save a file"
        name_filter: Final[str] = "Plain text files (*.log)"
        default_suffix: Final[str] = "log"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the save dialog."""

        pass

    def __init__(self, parent: QWidget = None):
        """Configure a save dialog targeting plain log files.

        Args:
            parent: Optional parent window for modality placement.
        """

        super().__init__(parent)
        self.texts = FileSaveDialog.Text()
        self.ui = FileSaveDialog.UI()

        self.setWindowTitle(self.texts.window_title)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setNameFilter(self.texts.name_filter)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setFilter(QDir.Filter.Files | QDir.Filter.Readable)
        self.setOptions(QFileDialog.Option.DontUseCustomDirectoryIcons)
        self.setDefaultSuffix(self.texts.default_suffix)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
