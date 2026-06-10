"""Activity log panel shell and backward-compatible activity exports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from PySide6.QtWidgets import QSizePolicy, QWidget

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
from gui.panel import CollapsiblePanel, CollapsiblePanelConfig
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import VerticalLayoutWrapper


class LogPanel(CollapsiblePanel):
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
        self.texts = LogPanel.Text()
        self.ui: LogPanel.UI
        self._activity_log_block: ActivityLogBlock
        super().__init__(
            CollapsiblePanelConfig(
                object_name="log-panel",
                title=self.texts.title,
                title_icon=GenericIcons.LOGS,
                expanded_icon=GenericIcons.LAYOUT_BOTTOMBAR_INSET,
                collapsed_icon=GenericIcons.LAYOUT_BOTTOMBAR,
                visibility_signal=signals.UI.LogPanelVisibilityRequested,
                expand_button_tooltip=self.texts.expand_button_tooltip,
            ),
            parent,
        )
        self.ui = LogPanel.UI(
            title=self.panel_title,
            expand_button=self.expand_button,
            header=self.header,
            body=self.body,
            activity_log_block=self._activity_log_block,
        )

    def _build_body(self) -> VerticalLayoutWrapper:
        """Build the activity-log body block."""
        self._activity_log_block = ActivityLogBlock(self)
        return VerticalLayoutWrapper(
            self,
            widgets=[self._activity_log_block],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )

    def _set_body_alignment(self) -> None:
        """Activity log body has no extra panel-owned alignment."""
        pass

    def _set_body_size_policy(self) -> None:
        """Set size policies for the activity log body."""
        self.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._activity_log_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_body_signals(self) -> None:
        """Activity log panel body has no extra signals."""
        pass

    def _apply_body_theme_icons(self, theme: Theme) -> None:
        """Refresh activity log block icons for ``theme``."""
        self._activity_log_block.apply_theme_icons(theme)

    def _after_panel_visibility_changed(self) -> None:
        """Refresh activity rows after visibility changes."""
        self.refresh_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_layout()

    def refresh_layout(self, *, deferred: bool = True) -> None:
        self.ui.activity_log_block.refresh_layout(deferred=deferred)

    def logs_list(self) -> List:
        return self.ui.activity_log_block.logs_list

    def file_display_widget(self) -> File:
        return self.ui.activity_log_block.file_display_widget


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
