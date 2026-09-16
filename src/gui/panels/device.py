"""Linked-device side panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.blocks.device import (
    DeviceSelectionBlock,
)
from gui.components import LeadingIconLabel
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons
from gui.constants.settings import Settings
from gui.panels.base import CollapsiblePanel, CollapsiblePanelConfig
from gui.wrapper import VerticalLayoutWrapper


class DeviceSelectionPanel(CollapsiblePanel):
    """Collapsible panel presenting linked Android devices."""

    @dataclass(frozen=True)
    class Text:
        """Panel-owned titles."""

        title: Final[str] = "Linked Devices"

    @dataclass
    class UI:
        """Panel-owned widgets."""

        title: LeadingIconLabel
        header: QWidget
        body: VerticalLayoutWrapper
        device_selection_block: DeviceSelectionBlock

    def __init__(self, parent: QWidget = None):
        """Build the device list panel with toolbar and state summary.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = DeviceSelectionPanel.Text()
        self.ui: DeviceSelectionPanel.UI
        self._device_selection_block: DeviceSelectionBlock
        super().__init__(
            CollapsiblePanelConfig(
                object_name="device-selection-panel",
                title=self.texts.title,
                title_icon=GenericIcons.DEVICE,
            ),
            parent,
        )
        self.ui = DeviceSelectionPanel.UI(
            title=self.panel_title,
            header=self.header,
            body=self.body,
            device_selection_block=self._device_selection_block,
        )

    def _build_body(self) -> VerticalLayoutWrapper:
        """Build the device-selection body block."""
        self._device_selection_block = DeviceSelectionBlock(self)
        body = VerticalLayoutWrapper(
            self,
            widgets=[self._device_selection_block],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        body.get_layout().setStretchFactor(self._device_selection_block, 1)
        return body

    def _set_body_alignment(self) -> None:
        """Device selection body has no extra panel-owned alignment."""
        pass

    def _set_body_size_policy(self) -> None:
        """Centralize size policies for panel-owned widgets."""
        self.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._device_selection_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_body_signals(self) -> None:
        """Device selection panel body has no extra signals."""
        pass

    def _apply_body_theme_icons(self, theme: Theme) -> None:
        """Refresh device-selection block icons for ``theme``."""
        self._device_selection_block.apply_theme_icons(theme)
