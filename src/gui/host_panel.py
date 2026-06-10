"""
This file contains all graphical elements related to the host panel.
"""

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.blocks.card import BridgeStatusCardBlock, IdentityCardBlock
from gui.colors import Theme
from gui.components import (
    LeadingIconLabel,
    ToolButton,
)
from gui.host_panel_settings import host_panel_settings
from gui.icons import GenericIcons
from gui.panel import CollapsiblePanel, CollapsiblePanelConfig
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import VerticalLayoutWrapper


class HostPanel(CollapsiblePanel):

    @dataclass(frozen=True)
    class Text:
        """Titles and tooltips owned by the host panel."""

        title: Final[str] = "Host device"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"

    @dataclass
    class UI:
        """Composed widgets for host identity, ADB status, and panel chrome."""

        title: LeadingIconLabel
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        identity_card: IdentityCardBlock
        bridge_card: BridgeStatusCardBlock

    def __init__(self, parent=None):
        """Build the host panel with grouped identity and ADB sections.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = HostPanel.Text()
        self.ui: HostPanel.UI
        self._is_extended = False
        self._identity_card: IdentityCardBlock
        self._bridge_card: BridgeStatusCardBlock
        super().__init__(
            CollapsiblePanelConfig(
                object_name="host-panel",
                title=self.texts.title,
                title_icon=GenericIcons.LAPTOP,
                expanded_icon=GenericIcons.LAYOUT_TOPBAR_INSET,
                collapsed_icon=GenericIcons.LAYOUT_TOPBAR,
                visibility_signal=signals.UI.HostPanelVisibilityRequested,
                expand_button_tooltip=self.texts.expand_button_tooltip,
                body_stretch=0,
            ),
            parent,
        )
        self.ui = HostPanel.UI(
            title=self.panel_title,
            expand_button=self.expand_button,
            header=self.header,
            body=self.body,
            identity_card=self._identity_card,
            bridge_card=self._bridge_card,
        )

    def _build_body(self) -> VerticalLayoutWrapper:
        """Build the host identity and bridge body."""
        self._identity_card = IdentityCardBlock(self)
        self._bridge_card = BridgeStatusCardBlock(self)
        self._bridge_card.setVisible(False)
        return VerticalLayoutWrapper(
            self,
            widgets=[self._identity_card, self._bridge_card],
            spacing=host_panel_settings.SECTION_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )

    def _set_body_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.body.get_layout().setAlignment(
            self._identity_card, Qt.AlignmentFlag.AlignTop
        )
        self.body.get_layout().setAlignment(
            self._bridge_card, Qt.AlignmentFlag.AlignTop
        )
        self.layout().setAlignment(self.body, Qt.AlignmentFlag.AlignTop)

    def _set_body_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self._identity_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._bridge_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_body_signals(self) -> None:
        """Host panel body has no extra signals."""
        pass

    def _apply_body_theme_icons(self, theme: Theme) -> None:
        """Refresh host and bridge card icons for ``theme``."""
        self._identity_card.apply_theme_icons(theme)
        self._bridge_card.apply_theme_icons(theme)

    def extend_panel(self) -> None:
        """Extend the host panel."""
        if not self._is_extended:
            self._is_extended = True
            self.ui.bridge_card.setVisible(True)
            self.updateGeometry()

    def shorten_panel(self) -> None:
        """Shorten the host panel."""
        if self._is_extended:
            self._is_extended = False
            self.ui.bridge_card.setVisible(False)
            self.updateGeometry()
