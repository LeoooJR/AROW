"""
This file contains all graphical elements related to the device panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.blocks.device import (
    DeviceSelectionBlock,
)
from gui.colors import Theme
from gui.components import (
    LeadingIconLabel,
    ToolButton,
)
from gui.icons import GenericIcons
from gui.panel import CollapsiblePanel, CollapsiblePanelConfig
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import (
    HorizontalLayoutWrapper,
    VerticalLayoutWrapper,
)


class DevicePairingPanel(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Copy for the device pairing side panel."""

        title: Final[str] = "Pairing Device"

    @dataclass
    class UI:
        """Chrome and body regions for pairing-specific content."""

        title: LeadingIconLabel
        header: HorizontalLayoutWrapper
        body: HorizontalLayoutWrapper

    def __init__(self, parent: QWidget = None):
        """Create the pairing panel shell (title + expandable body host).

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: DevicePairingPanel.UI
        self.texts = DevicePairingPanel.Text()

        self.setObjectName("device-pairing-panel")
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

        title = LeadingIconLabel(
            parent=None,
            icon=GenericIcons.DEVICE,
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
            properties={"panel-title": True, "main-panel-title": True},
            label_properties={"section-title": True},
            constrain_to_size_hint=True,
        )

        header = HorizontalLayoutWrapper(
            self,
            widgets=[title],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(header, 0)

        body = HorizontalLayoutWrapper(
            self,
            widgets=[],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body, 1)

        self.setLayout(layout)

        self.ui = DevicePairingPanel.UI(title=title, header=header, body=body)

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.title.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the device pairing panel."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Centralize size policies for the device pairing panel."""
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        """Centralize alignment for the device pairing panel."""
        self.layout().setAlignment(self.ui.header, Qt.AlignmentFlag.AlignLeft)
        self.ui.header.get_layout().setAlignment(
            self.ui.title, Qt.AlignmentFlag.AlignLeft
        )

    def _connect_signals(self) -> None:
        """Connect signals for the device pairing panel."""
        pass


class DeviceSelectionPanel(CollapsiblePanel):

    @dataclass(frozen=True)
    class Text:
        """Panel-owned titles and tooltips."""

        title: Final[str] = "Linked Devices"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"

    @dataclass
    class UI:
        """Panel-owned widgets."""

        title: LeadingIconLabel
        expand_button: ToolButton
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
                expanded_icon=GenericIcons.LAYOUT_TOPBAR_INSET,
                collapsed_icon=GenericIcons.LAYOUT_TOPBAR,
                visibility_signal=signals.UI.DeviceSelectionPanelVisibilityRequested,
                expand_button_tooltip=self.texts.expand_button_tooltip,
            ),
            parent,
        )
        self.ui = DeviceSelectionPanel.UI(
            title=self.panel_title,
            expand_button=self.expand_button,
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
