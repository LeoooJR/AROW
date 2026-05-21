"""
This file contains all graphical elements related to the host panel.
"""

from dataclasses import dataclass
from typing import Final, Literal

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
from gui.colors import Theme
from gui.components import (
    LeadingIconLabel,
    ToolButton,
)
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
)
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import VerticalLayoutWrapper

from gui.blocks.card import ADB_SERVER_STATE, BridgeStatusCardBlock, IdentityCardBlock


class HostPanel(QFrame):

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
        super().__init__(parent)

        self.ui: HostPanel.UI
        self.texts = HostPanel.Text()

        self._is_extended = False

        self.setObjectName("host-panel")
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
            icon=GenericIcons.LAPTOP,
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

        identity_card = IdentityCardBlock(self)
        bridge_card = BridgeStatusCardBlock(self)
        bridge_card.setVisible(False)

        body = VerticalLayoutWrapper(
            self,
            widgets=[identity_card, bridge_card],
            spacing=Settings.HOST_PANEL.SECTION_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body)

        self.setLayout(layout)

        self.ui = HostPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            identity_card=identity_card,
            bridge_card=bridge_card,
        )

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the host panel."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.ui.body.get_layout().setAlignment(
            self.ui.identity_card, Qt.AlignmentFlag.AlignTop
        )
        self.ui.body.get_layout().setAlignment(
            self.ui.bridge_card, Qt.AlignmentFlag.AlignTop
        )
        self.layout().setAlignment(self.ui.body, Qt.AlignmentFlag.AlignTop)

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.identity_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.bridge_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        # Preferred vertically so the panel can shrink when the bridge card is hidden.
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the host panel and its UI widgets."""
        #### Signals for toggling the host panel visibility ####
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: view_signals.HostPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

        view_signals.ADBServerStarted.connect(self._on_adb_server_started)
        view_signals.ADBServerStopped.connect(self._on_adb_server_stopped)

        view_signals.HostDeviceInformationUpdated.connect(
            self._on_host_device_information_updated
        )

    def _on_adb_server_started(self) -> None:
        """Handle the ADB server started event."""
        self.set_adb_bridge_values(server_state="running", indicator_state="valid")

    def _on_adb_server_stopped(self) -> None:
        """Handle the ADB server stopped event."""
        self.set_adb_bridge_values(server_state="stopped", indicator_state="error")

    def set_host_identity_values(
        self,
        host_name: str | None = None,
        summary: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        os_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
        identity_state: str | None = None,
    ) -> None:
        """Set the values for the host identity section."""
        self.ui.identity_card.set_host_values(
            host_name=host_name,
            summary=summary,
            ip_address=ip_address,
            platform=platform,
            os_icon=os_icon,
            identity_state=identity_state,
        )

    def set_adb_bridge_values(
        self,
        server_state: ADB_SERVER_STATE | None = None,
        server_state_text: str | None = None,
        adb_version: str | None = None,
        daemon: str | None = None,
        connected_devices: str | None = None,
        helper_note: str | None = None,
        indicator_state: str | None = None,
    ) -> None:
        """Set the values for the adb bridge section."""
        self.ui.bridge_card.set_adb_values(
            server_state=server_state,
            server_state_text=server_state_text,
            adb_version=adb_version,
            daemon=daemon,
            connected_devices=connected_devices,
            helper_note=helper_note,
            indicator_state=indicator_state,
        )

    def _on_host_device_information_updated(
        self, name: str, os: Literal["linux", "windows", "darwin"] | None, ip: str
    ) -> None:
        """Handle the host device information updated."""
        assert os in ["linux", "windows", "darwin"]
        if os == "linux":
            os_icon = OperatingSystemIcons.LINUX
        elif os == "windows":
            os_icon = OperatingSystemIcons.WINDOWS
        elif os == "darwin":
            os_icon = OperatingSystemIcons.MACOS
        else:
            os_icon = GenericIcons.LAPTOP
        self.set_host_identity_values(
            host_name=name,
            ip_address=ip,
            platform=os,
            os_icon=os_icon,
            identity_state="valid",
        )

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh header, host glyph, expand control, and ADB block icon for ``theme``."""
        self.ui.title.apply_theme_icons(theme)
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_TOPBAR_INSET if inset else GenericIcons.LAYOUT_TOPBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.identity_card.apply_theme_icons(theme)
        self.ui.bridge_card.apply_theme_icons(theme)

    def is_panel_visible(self) -> bool:
        """Check if the host panel is visible."""
        return bool(self.ui.expand_button.property("toggle"))

    def show_panel(self) -> None:
        """Show the host panel."""
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
        """Hide the host panel."""
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

    def _reduced_height(self) -> int:
        """Height of the panel when reduced (header only): layout padding + header size."""
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the host panel."""
        if self.ui.expand_button.property("toggle"):
            # Reduce: hide body and constrain height so the panel under can grow.
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR)
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        else:
            # Expand: show body and allow it to grow.
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        # Notify parent layout so space is reallocated (panel below gets more height when reduced).
        self.updateGeometry()

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
