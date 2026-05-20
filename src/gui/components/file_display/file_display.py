"""File summary row display component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid

from gui.colors import Theme
from gui.components.base.component import Component
from gui.components.buttons.tool_button import ToolButton
from gui.components.dialogs.file_dialog import FileSaveDialog
from gui.components.labels.helper_text import HelperText
from gui.components.media.svg import SVG
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.components.media import get_svg_size


class File(QWidget, Component):
    """
    Widget that displays a file (icon, name, format). Styled via stylesheet (file-display, file-icon-wrapper, file-name).
    Filename is elided with ellipsis when too long. Do not add a close button.
    """

    @dataclass(frozen=True)
    class Text:
        """File row labels and save-as tooltip."""

        file_name: str = ""
        file_type: str = ""
        save_as_tooltip: Final[str] = "Save as"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the file row."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        file_name: str,
        file_type: str,
        file_save: bool = False,
    ):
        """Render a file summary row with optional save-as affordance.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            file_name: Display name for the file.
            file_type: Short type label (e.g. extension category).
            file_save: When True, show a save-as tool button.
        """
        super().__init__(parent)
        self.texts = File.Text(file_name=file_name, file_type=file_type)
        self.ui = File.UI()

        self.setProperty("file", True)
        self.setObjectName("file-display")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._file_name = file_name
        self._file_save = file_save

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.ICON_SPACING)

        file_icon_wrapper = QWidget(self)
        file_icon_wrapper.setObjectName("file-icon-wrapper")
        file_icon_wrapper.setLayout(QVBoxLayout())
        file_icon_wrapper.layout().setContentsMargins(0, 0, 0, 0)
        file_icon = SVG(icon_qt_path(GenericIcons.FILE), file_icon_wrapper)
        file_icon.setFixedSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
        file_icon_wrapper.layout().addWidget(file_icon)
        file_icon_wrapper.layout().setAlignment(file_icon, Qt.AlignmentFlag.AlignCenter)
        self._file_icon = file_icon
        layout.addWidget(file_icon_wrapper)
        layout.setAlignment(
            file_icon_wrapper,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )

        file_description = QWidget(self)
        file_description.setObjectName("file-description")
        file_description.setLayout(QVBoxLayout())
        file_description.layout().setContentsMargins(0, 0, 0, 0)
        file_description.layout().setSpacing(2)
        file_name_label = QLabel(file_name, file_description)
        file_name_label.setObjectName("file-name")
        file_name_label.setWordWrap(False)
        file_description.layout().addWidget(file_name_label)
        file_description.layout().setAlignment(
            file_name_label, Qt.AlignmentFlag.AlignLeft
        )

        file_type_label = HelperText(file_description, file_type.upper())
        file_description.layout().addWidget(file_type_label)
        file_description.layout().setAlignment(
            file_type_label, Qt.AlignmentFlag.AlignLeft
        )
        self._file_description = file_description
        self._file_type_label = file_type_label
        layout.addWidget(file_description, 1)
        layout.setAlignment(
            file_description, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        if self._file_save:
            save_as_button = ToolButton(
                self,
                icon=GenericIcons.SAVE_AS,
                tooltip=self.texts.save_as_tooltip,
            )
            layout.addWidget(save_as_button)
            layout.setAlignment(save_as_button, Qt.AlignmentFlag.AlignRight)
            self._save_as_button = save_as_button

        self._file_name_label = file_name_label
        self.setLayout(layout)
        self._pending_name_elide_update: bool = False
        self._pending_name_elide_retry: bool = False
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        if hasattr(self, "_save_as_button"):
            self._save_as_button.clicked.connect(self._on_save_as_button_clicked)

    def apply_theme_icons(self, theme: Theme) -> None:
        self._file_icon.set_path(icon_qt_path_for_theme(theme, GenericIcons.FILE))
        if hasattr(self, "_save_as_button"):
            self._save_as_button.apply_theme_icons(theme)

    def _on_save_as_button_clicked(self) -> None:
        """Handle the save as button click event."""
        dialog = FileSaveDialog(self)
        if dialog.exec():
            filename: list[str] = dialog.selectedFiles()
            if filename:
                view_signals.SimulationLogFileUpdateRequested.emit(filename[0])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_display()

    def refresh_display(self) -> None:
        """Refresh filename/type layout after parent geometry changes."""
        if not isValid(self):
            return
        if not self._file_name or not self._file_name_label:
            return
        if not isValid(self._file_name_label):
            return

        if self._file_name_label.text() != self._file_name:
            self._file_name_label.setText(self._file_name)

        for widget in (self, self._file_description, self._file_name_label):
            if widget.layout() is not None:
                widget.layout().activate()
            widget.updateGeometry()

        if not self._pending_name_elide_update:
            self._pending_name_elide_update = True
            QTimer.singleShot(0, self._update_file_name_display)

    def _file_name_available_width(self) -> int:
        """Best-effort content width for filename elision."""
        widths: list[int] = []
        if isValid(self._file_name_label):
            widths.append(self._file_name_label.width())
        if isValid(self._file_description):
            widths.append(self._file_description.contentsRect().width())
        positive_widths = [width for width in widths if width > 0]
        return min(positive_widths) if positive_widths else 0

    def _update_file_name_display(self) -> None:
        self._pending_name_elide_update = False
        if not isValid(self):
            return
        if not self._file_name or not self._file_name_label:
            return
        if not isValid(self._file_name_label):
            return

        fm = QFontMetrics(self._file_name_label.font())
        available_w = self._file_name_available_width()
        if (
            available_w <= 0
            or not self.isVisible()
            or not self._file_name_label.isVisible()
        ):
            if self._file_name_label.text() != self._file_name:
                self._file_name_label.setText(self._file_name)
            if (
                self.isVisible()
                and self._file_name_label.isVisible()
                and not self._pending_name_elide_retry
            ):
                self._pending_name_elide_retry = True
                self._pending_name_elide_update = True
                QTimer.singleShot(0, self._update_file_name_display)
            return
        self._pending_name_elide_retry = False

        # Only elide when the full text doesn't fit in the current available width.
        # This preserves short filenames when there is enough space.
        full_text_w = fm.horizontalAdvance(self._file_name)
        fudge_px = Settings.SPACING.XS  # small margin for sub-pixel/font rounding
        if full_text_w <= available_w - fudge_px:
            if self._file_name_label.text() != self._file_name:
                self._file_name_label.setText(self._file_name)
            return

        elided = fm.elidedText(
            self._file_name, Qt.TextElideMode.ElideRight, available_w
        )
        if self._file_name_label.text() != elided:
            self._file_name_label.setText(elided)

    def set_file_display(self, file_name: str, file_type: str) -> None:
        """Update the displayed file name and type (labels and elision state)."""
        self._file_name = file_name
        self.texts = File.Text(file_name=file_name, file_type=file_type)
        self._file_type_label.setText(file_type.upper())
        self._pending_name_elide_retry = False
        self.refresh_display()
