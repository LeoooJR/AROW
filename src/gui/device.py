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
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.animation import animate_widget_visibility
from gui.blocks.device import (
    DeviceSelectionBlock,
)
from gui.colors import Theme
from gui.components import (
    LeadingIconLabel,
    ToolButton,
)
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import view_signals
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

        self.ui: DevicePairingPanel.UI = DevicePairingPanel.UI(
            title=title, header=header, body=body
        )

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


class DeviceSelectionPanel(QFrame):

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
        super().__init__(parent)

        self.ui: DeviceSelectionPanel.UI
        self.texts = DeviceSelectionPanel.Text()

        self.setObjectName("device-selection-panel")
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
            parent=self,
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
            label_properties={"section-title": True},
            constrain_to_size_hint=True,
        )

        expand_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_TOPBAR_INSET,
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

        device_selection_block = DeviceSelectionBlock(self)

        body = VerticalLayoutWrapper(
            self,
            widgets=[device_selection_block],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        body.get_layout().setStretchFactor(device_selection_block, 1)
        layout.addWidget(body, 1)

        self.setLayout(layout)

        self.ui: DeviceSelectionPanel.UI = DeviceSelectionPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            device_selection_block=device_selection_block,
        )

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the device selection panel."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for panel-owned widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for panel-owned widgets."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.device_selection_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_signals(self) -> None:
        """Connect signals for the device selection panel and its UI widgets."""
        #### Signals for toggling the device selection panel visibility ####
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: view_signals.DeviceSelectionPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

    def is_panel_visible(self) -> bool:
        """Check if the device selection panel is visible."""
        return bool(self.ui.expand_button.property("toggle"))

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh toolbar, header, empty state, and row icons for ``theme``."""
        self.ui.title.apply_theme_icons(theme)
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_TOPBAR_INSET if inset else GenericIcons.LAYOUT_TOPBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.device_selection_block.apply_theme_icons(theme)

    def _reduced_height(self) -> int:
        """Height of the panel when reduced (header only): layout padding + header size."""
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        """Show the device selection panel."""
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )

    def hide_panel(self) -> None:
        """Hide the device selection panel."""
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR)
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the device selection panel."""
        if self.is_panel_visible():
            # Reduce: hide body and constrain height so the panel under can grow.
            self.hide_panel()
        else:
            # Expand: show body and allow panel to grow again.
            self.show_panel()
        # Notify parent layout so space is reallocated (panel below gets more height when reduced).
        self.updateGeometry()
