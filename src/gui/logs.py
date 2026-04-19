"""
This file contains all graphical elements related to the logs panel.
"""

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from gui.elements import (
    File,
    FileSaveDialog,
    GroupBox,
    HelperText,
    List,
    PanelTitle,
    ToolButton,
)
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import app_signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class LogPanel(QFrame):
    """Side panel listing activity logs and the log file summary."""

    @dataclass(frozen=True)
    class Text:
        """Titles, placeholders, and helper copy for the log panel."""

        title: Final[str] = "Activity log"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"
        placeholder_items: Final[tuple[str, ...]] = ("Log 1", "Log 2", "Log 3")
        helper_text: Final[str] = "Logs are saved in the following file"
        file_name: Final[str] = "test.log"
        file_type: Final[str] = "TXT"
        group_title: Final[str] = "Logs"

    @dataclass
    class UI:
        """Widgets for the log list, file row, and grouped layout."""

        title: PanelTitle
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        logs_list: List
        logs_list_helper_text: HelperText
        file_display_widget: File
        logs_wrapper: VerticalLayoutWrapper
        logs_group_box: GroupBox

    def __init__(self, parent=None):
        """Build the log panel layout and wire expand behavior.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: LogPanel.UI
        self.texts = LogPanel.Text()

        self.setObjectName("log-panel")
        self.setProperty("panel", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(
            Settings.PANEL.SECTION_SPACING
        )  # Consistent spacing between major sections

        title = PanelTitle(
            parent=self, text=self.texts.title, icon_path=GenericIcons.LOGS.value
        )

        expand_button = ToolButton(
            self,
            icon_path=GenericIcons.LAYOUT_BOTTOMBAR_INSET.value,
            tooltip=self.texts.expand_button_tooltip,
        )
        expand_button.setProperty("toggle", True)

        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        header_layout.setSpacing(Settings.SPACING.NONE)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(expand_button)
        layout.addWidget(header)

        logs_list = List(None)
        logs_list.setObjectName("logs-list")
        self.add_list_items_placeholder(
            logs_list, items=list(self.texts.placeholder_items)
        )
        logs_list_helper_text = HelperText(self, self.texts.helper_text)

        file_display_widget = File(
            None,
            file_name=self.texts.file_name,
            file_type=self.texts.file_type,
            file_save=True,
        )

        logs_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[logs_list, file_display_widget, logs_list_helper_text],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        logs_wrapper.get_layout().setStretchFactor(logs_list, 1)
        logs_wrapper.get_layout().setStretchFactor(file_display_widget, 0)
        logs_wrapper.get_layout().setStretchFactor(logs_list_helper_text, 0)

        logs_group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[logs_wrapper],
            title=self.texts.group_title,
        )
        logs_group_box.setObjectName("logs-group-box")

        body = VerticalLayoutWrapper(
            self,
            widgets=[logs_group_box],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body, 1)

        self.ui: LogPanel.UI = LogPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            logs_group_box=logs_group_box,
            logs_wrapper=logs_wrapper,
            logs_list=logs_list,
            logs_list_helper_text=logs_list_helper_text,
            file_display_widget=file_display_widget,
        )

        self.setLayout(layout)

        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.ui.logs_wrapper.get_layout().setAlignment(
            self.ui.logs_list_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.logs_wrapper.get_layout().setAlignment(
            self.ui.file_display_widget, Qt.AlignmentFlag.AlignLeft
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.logs_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.logs_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.logs_group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.logs_list_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.file_display_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_signals(self) -> None:
        """Connect signals for the log panel and its UI widgets."""
        #### Signals for toggling the log panel visibility ####
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: app_signals.LogPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

    def is_panel_visible(self) -> bool:
        """Check if the log panel is visible."""
        return self.ui.body.isVisible()

    def _reduced_height(self) -> int:
        """Height of the panel when reduced (header only): layout padding + header size."""
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        """Show the log panel."""
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(
                QIcon(GenericIcons.LAYOUT_BOTTOMBAR_INSET.value)
            )
            self.ui.body.setVisible(True)
            self.setMaximumHeight(Settings.PANEL.UNBOUNDED_HEIGHT)
            self.updateGeometry()

    def hide_panel(self) -> None:
        """Hide the log panel."""
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_BOTTOMBAR.value))
            self.ui.body.setVisible(False)
            self.setMaximumHeight(self._reduced_height())
            self.updateGeometry()

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the log panel."""
        if self.ui.expand_button.property("toggle"):
            # Reduce: hide body and constrain height so the panel under can grow.
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_BOTTOMBAR.value))
            self.ui.body.setVisible(False)
            self.setMaximumHeight(self._reduced_height())
        else:
            # Expand: show body and allow it to grow.
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(
                QIcon(GenericIcons.LAYOUT_BOTTOMBAR_INSET.value)
            )
            self.ui.body.setVisible(True)
            self.setMaximumHeight(Settings.PANEL.UNBOUNDED_HEIGHT)
        # Notify parent layout so space is reallocated (panel below gets more height when reduced).
        self.updateGeometry()

    def add_list_items_placeholder(self, list_widget: List, items: list[str]) -> None:
        """Add placeholder items to the list widget.

        Args:
            list_widget: Target list widget.
            items: String labels to insert as rows.
        """
        list_widget.add_items([item for item in items])
