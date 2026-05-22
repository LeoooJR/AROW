"""Activity log panel shell and backward-compatible activity exports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from gui.animation import animate_widget_visibility
from gui.blocks.activity import (
    ActivityCategory,
    ActivityDateHeaderItem,
    ActivityFilterOption,
    ActivityFilterSectionLabel,
    ActivityFilterSeparator,
    ActivityLevel,
    ActivityLogBlock,
    ActivityLogEntry,
    ActivityLogItem,
)
from gui.colors import Theme
from gui.components import File, LeadingIconLabel, List, ToolButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import VerticalLayoutWrapper


class LogPanel(QFrame):
    """Side-panel shell for the activity log block."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Activity log"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"

    @dataclass
    class UI:
        title: LeadingIconLabel
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        activity_log_block: ActivityLogBlock

    def __init__(self, parent=None):
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
        layout.setSpacing(Settings.PANEL.SECTION_SPACING)

        title = LeadingIconLabel(
            parent=self,
            icon=GenericIcons.LOGS,
            text=self.texts.title,
            font_size=Settings.FONT.SIZE_TITLE,
            font_weight=QFont.Weight.DemiBold,
            spacing=Settings.PANEL.TITLE_ICON_SPACING,
            margins=(
                Settings.PANEL.TITLE_PADDING_LEFT,
                Settings.PANEL.TITLE_PADDING_TOP,
                Settings.PANEL.TITLE_PADDING_RIGHT,
                Settings.PANEL.TITLE_PADDING_BOTTOM,
            ),
            text_alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label_properties={"section-title": True},
            constrain_to_size_hint=True,
        )

        expand_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_BOTTOMBAR_INSET,
            tooltip=self.texts.expand_button_tooltip,
        )
        expand_button.setProperty("toggle", True)

        header = QWidget(self)
        header.setProperty("panel-title", True)
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        header_layout.setSpacing(Settings.SPACING.NONE)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(expand_button)
        layout.addWidget(header)

        activity_log_block = ActivityLogBlock(self)
        body = VerticalLayoutWrapper(
            self,
            widgets=[activity_log_block],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body, 1)

        self.setLayout(layout)

        self.ui = LogPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            activity_log_block=activity_log_block,
        )

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.activity_log_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_signals(self) -> None:
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: view_signals.LogPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

    def is_panel_visible(self) -> bool:
        return bool(self.ui.expand_button.property("toggle"))

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.title.apply_theme_icons(theme)
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_BOTTOMBAR_INSET
            if inset
            else GenericIcons.LAYOUT_BOTTOMBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.activity_log_block.apply_theme_icons(theme)

    def _reduced_height(self) -> int:
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        self.refresh_layout()

    def hide_panel(self) -> None:
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR)
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        self.refresh_layout()

    def toggle_panel_visibility(self) -> None:
        if self.ui.expand_button.property("toggle"):
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR)
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        else:
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        self.updateGeometry()
        self.refresh_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_layout()

    def refresh_layout(self, *, deferred: bool = True) -> None:
        self.ui.activity_log_block.refresh_layout(deferred=deferred)

    def logs_list(self) -> List:
        return self.ui.activity_log_block.logs_list()

    def file_display_widget(self) -> File:
        return self.ui.activity_log_block.file_display_widget()


__all__ = [
    "ActivityCategory",
    "ActivityDateHeaderItem",
    "ActivityFilterOption",
    "ActivityFilterSectionLabel",
    "ActivityFilterSeparator",
    "ActivityLevel",
    "ActivityLogBlock",
    "ActivityLogEntry",
    "ActivityLogItem",
    "LogPanel",
]
