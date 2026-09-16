"""Activity log panel shell and backward-compatible activity exports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Slot
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
from gui.components import File, LeadingIconLabel, List
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons
from gui.constants.settings import Settings
from gui.panels.base import CollapsiblePanel, CollapsiblePanelConfig
from gui.wrapper import VerticalLayoutWrapper


class LogPanel(CollapsiblePanel):
    """Side-panel shell for the activity log block."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Activity log"

    @dataclass
    class UI:
        title: LeadingIconLabel
        header: QWidget
        body: VerticalLayoutWrapper
        activity_log_block: ActivityLogBlock

    def __init__(self, parent=None):
        """Build the collapsible activity-log panel.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = LogPanel.Text()
        self.ui: LogPanel.UI
        self._activity_log_block: ActivityLogBlock
        super().__init__(
            CollapsiblePanelConfig(
                object_name="log-panel",
                title=self.texts.title,
                title_icon=GenericIcons.LOGS,
            ),
            parent,
        )
        self.ui = LogPanel.UI(
            title=self.panel_title,
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

    def resizeEvent(self, event) -> None:
        """Refresh the activity-log layout after the panel is resized."""
        super().resizeEvent(event)
        self.refresh_layout()

    @Slot()
    def refresh_layout(self, *, deferred: bool = True) -> None:
        """Refresh responsive activity-log layout state.

        Args:
            deferred: Whether to defer geometry-dependent work to the event loop.
        """
        self.ui.activity_log_block.refresh_layout(deferred=deferred)

    def logs_list(self) -> List:
        """Return the activity log list widget."""
        return self.ui.activity_log_block.logs_list

    def file_display_widget(self) -> File:
        """Return the activity log file summary widget."""
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
