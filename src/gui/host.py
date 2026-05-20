"""
This file contains all graphical elements related to the host panel.
"""

from dataclasses import dataclass, field
from typing import Final, Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import faker as ui_faker
from gui.animation import animate_widget_visibility
from gui.colors import Theme
from gui.components import (
    SVG,
    ConditionIndicator,
    GroupBox,
    LeadingIconLabel,
    PanelTitle,
    ToolButton,
)
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.signals import view_signals
from gui.svg import get_svg_size
from gui.wrapper import GridLayoutWrapper, VerticalLayoutWrapper

ADB_SERVER_STATE = Literal["running", "stopped", "starting", "error", "unknown"]


class HostIdentityMetadataRow(QWidget):
    """Key/value row for HostIdentitySection only; stylesheet uses host-identity-metadata-row."""

    @dataclass(frozen=True)
    class Text:
        """Left/right copy for a host identity metadata row."""

        key: str = ""
        value: str = ""

    @dataclass
    class UI:
        """Labels backing the metadata row."""

        key: QLabel
        value: QLabel

    def __init__(self, key_text: str, value_text: str, parent: QWidget | None = None):
        """Build a labeled key/value row.

        Args:
            key_text: Label shown on the left.
            value_text: Value shown on the right.
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: HostIdentityMetadataRow.UI
        self.texts = HostIdentityMetadataRow.Text(key=key_text, value=value_text)
        self.setProperty("host-identity-metadata-row", True)

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.HOST_PANEL.KEY_VALUE_SPACING)

        key = QLabel(self.texts.key, self)
        key.setProperty("host-metadata-key", True)
        key.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        value = QLabel(self.texts.value, self)
        value.setProperty("host-metadata-value", True)
        value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        layout.addWidget(key)
        layout.addStretch()
        layout.addWidget(value)
        layout.setAlignment(value, Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)
        self.ui = HostIdentityMetadataRow.UI(key=key, value=value)
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the host identity metadata row."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.key.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.value.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.layout().setAlignment(
            self.ui.key, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.layout().setAlignment(
            self.ui.value, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def _connect_signals(self) -> None:
        pass

    def set_key_text(self, text: str) -> None:
        """Update the left label text.

        Args:
            text: New key label string.
        """
        self.ui.key.setText(text)

    def set_value_text(self, text: str) -> None:
        """Update the right label text.

        Args:
            text: New value string.
        """
        self.ui.value.setText(text)


class AdbBridgeMetadataRow(QWidget):
    """Key/value row for AdbBridgeSection only; supports adb-server-state coloring on the value."""

    @dataclass(frozen=True)
    class Text:
        """Left/right copy for an ADB bridge metadata row."""

        key: str = ""
        value: str = ""

    @dataclass
    class UI:
        """Labels backing the ADB metadata row."""

        key: QLabel
        value: QLabel

    def __init__(self, key_text: str, value_text: str, parent: QWidget | None = None):
        """Build a labeled key/value row with optional ADB state styling on the value.

        Args:
            key_text: Label shown on the left.
            value_text: Value shown on the right.
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: AdbBridgeMetadataRow.UI
        self.texts = AdbBridgeMetadataRow.Text(key=key_text, value=value_text)
        self.setProperty("adb-bridge-metadata-row", True)

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.HOST_PANEL.KEY_VALUE_SPACING)

        key = QLabel(self.texts.key, self)
        key.setProperty("host-metadata-key", True)
        key.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        value = QLabel(self.texts.value, self)
        value.setProperty("host-metadata-value", True)
        value.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        layout.addWidget(key)
        layout.addStretch()
        layout.addWidget(value)
        layout.setAlignment(value, Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)
        self.ui = AdbBridgeMetadataRow.UI(key=key, value=value)
        self.set_value_state("default")
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the ADB bridge metadata row."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.key.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.value.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.layout().setAlignment(
            self.ui.key, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.layout().setAlignment(
            self.ui.value, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def _connect_signals(self) -> None:
        pass

    def set_key_text(self, text: str) -> None:
        """Update the left label text.

        Args:
            text: New key label string.
        """
        self.ui.key.setText(text)

    def set_value_text(self, text: str) -> None:
        """Update the right label text.

        Args:
            text: New value string.
        """
        self.ui.value.setText(text)

    def set_value_state(self, state: str = "default") -> None:
        """Apply stylesheet state token on the value label (e.g. running/stopped).

        Args:
            state: Property value for ``adb-server-state`` on the value label.
        """
        self.ui.value.setProperty("adb-server-state", state)
        self.ui.value.style().unpolish(self.ui.value)
        self.ui.value.style().polish(self.ui.value)
        self.ui.value.update()


class HostIdentitySection(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Default copy for host title, summary, and identity rows."""

        host_name: Final[str] = "Unknown Host"
        host_summary: Final[str] = (
            "Primary workstation ready for location spoofing workflow."
        )
        ip_address_key: Final[str] = "Local IP"
        ip_address_value: Final[str] = "N/A"
        platform_key: Final[str] = "Platform"
        platform_value: Final[str] = "N/A"

    @dataclass
    class UI:
        """Widgets for the host identity block."""

        host_name: QLabel
        host_summary: QLabel
        host_item: LeadingIconLabel
        ip_address_row: HostIdentityMetadataRow
        platform_row: HostIdentityMetadataRow

    def __init__(self, parent: QWidget | None = None):
        """Build the host identity section with placeholder data.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: HostIdentitySection.UI
        self.texts = HostIdentitySection.Text()
        self.setObjectName("host-identity-section")
        self.setProperty("panel-section-compact", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.HOST_PANEL.ROW_SPACING)

        host_name = QLabel(self.texts.host_name, self)
        host_name.setProperty("host-title", True)

        host_item = LeadingIconLabel(
            self,
            icon=OperatingSystemIcons.MACOS,
            text=host_name,
            spacing=Settings.SPACING.ICON_SPACING,
        )

        host_summary = QLabel(self.texts.host_summary, self)
        host_summary.setProperty("host-supporting-text", True)
        host_summary.setWordWrap(True)

        ip_address_row = HostIdentityMetadataRow(
            self.texts.ip_address_key, self.texts.ip_address_value, self
        )
        platform_row = HostIdentityMetadataRow(
            self.texts.platform_key, self.texts.platform_value, self
        )

        layout.addWidget(host_item)
        layout.addWidget(host_summary)
        layout.addWidget(ip_address_row)
        layout.addWidget(platform_row)

        self.setLayout(layout)
        self.ui = HostIdentitySection.UI(
            host_name=host_name,
            host_summary=host_summary,
            host_item=host_item,
            ip_address_row=ip_address_row,
            platform_row=platform_row,
        )
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the host identity section."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.host_item.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.host_summary.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.ip_address_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.platform_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.layout().setAlignment(self.ui.host_item, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.host_summary,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _connect_signals(self) -> None:
        pass

    def set_host_values(
        self,
        host_name: str | None = None,
        summary: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        os_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
    ) -> None:
        """Update displayed host fields; omit arguments to leave them unchanged.

        Args:
            host_name: Machine or host display name.
            summary: Short supporting description under the title.
            ip_address: Local IP string for the IP row.
            platform: Platform string for the platform row.
            os_icon: Icon enum for the host operating system row.
        """
        if host_name is not None:
            self.ui.host_name.setText(host_name)
        if summary is not None:
            self.ui.host_summary.setText(summary)
        if ip_address is not None:
            self.ui.ip_address_row.set_value_text(ip_address)
        if platform is not None:
            self.ui.platform_row.set_value_text(platform)
        if os_icon is not None:
            self.ui.host_item.set_icon(os_icon)


class AdbBridgeSection(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Labels and default values for the ADB status block."""

        status_key: Final[str] = "Server state"
        status_value: Final[str] = "unknown"
        version_key: Final[str] = "ADB version"
        version_value: Final[str] = "N/A"
        daemon_key: Final[str] = "Daemon"
        daemon_value: Final[str] = "N/A"
        devices_key: Final[str] = "Connected devices"
        devices_value: Final[str] = "N/A"
        helper_note: Final[str] = (
            "Binary allowing communication between Android devices and the host computer."
        )

    @dataclass
    class UI:
        """Widgets for the ADB bridge summary and helper note."""

        android_svg: SVG
        status_row: AdbBridgeMetadataRow
        version_row: AdbBridgeMetadataRow
        daemon_row: AdbBridgeMetadataRow
        devices_row: AdbBridgeMetadataRow
        helper_note: QLabel

    def __init__(self, parent: QWidget | None = None):
        """Build the ADB bridge section with placeholder metrics.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: AdbBridgeSection.UI
        self.texts = AdbBridgeSection.Text()
        self.setObjectName("adb-bridge-section")
        self.setProperty("panel-section-compact", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.HOST_PANEL.ROW_SPACING)

        android_svg = SVG(
            svg_path=icon_qt_path(OperatingSystemIcons.ANDROID), parent=self
        )
        android_svg.setFixedSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))

        status_row = AdbBridgeMetadataRow(
            self.texts.status_key, self.texts.status_value, self
        )
        status_row.setObjectName("adb-status-row")
        status_row.setProperty("adb-status-row", True)
        version_row = AdbBridgeMetadataRow(
            self.texts.version_key, self.texts.version_value, self
        )
        daemon_row = AdbBridgeMetadataRow(
            self.texts.daemon_key, self.texts.daemon_value, self
        )
        devices_row = AdbBridgeMetadataRow(
            self.texts.devices_key, self.texts.devices_value, self
        )
        devices_row.setObjectName("adb-devices-row")

        helper_note = QLabel(self.texts.helper_note, self)
        helper_note.setProperty("host-supporting-text", True)
        helper_note.setWordWrap(True)
        helper_note.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(android_svg)
        layout.addWidget(status_row)
        layout.addWidget(version_row)
        layout.addWidget(daemon_row)
        layout.addWidget(devices_row)
        layout.addWidget(helper_note)

        self.setLayout(layout)
        self.ui = AdbBridgeSection.UI(
            android_svg=android_svg,
            status_row=status_row,
            version_row=version_row,
            daemon_row=daemon_row,
            devices_row=devices_row,
            helper_note=helper_note,
        )
        self.set_server_state("running")

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the ADB bridge section."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.android_svg.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.status_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.version_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.daemon_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.helper_note.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.layout().setAlignment(self.ui.android_svg, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.helper_note,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _connect_signals(self) -> None:
        pass

    def set_server_state(
        self, state: ADB_SERVER_STATE, text: str | None = None
    ) -> None:
        """Show ADB server state with optional custom label text.

        Args:
            state: Logical server state token for styling.
            text: Optional override for the displayed status string.
        """
        display_text = text if text is not None else state.capitalize()
        self.ui.status_row.set_value_text(display_text)
        self.ui.status_row.set_value_state(state)

    def set_adb_values(
        self,
        server_state: ADB_SERVER_STATE | None = None,
        server_state_text: str | None = None,
        adb_version: str | None = None,
        daemon: str | None = None,
        connected_devices: str | None = None,
        helper_note: str | None = None,
    ) -> None:
        """Update ADB-related rows; omit arguments to leave values unchanged.

        Args:
            server_state: When set, drives status row text and state styling.
            server_state_text: Optional status label when not using ``server_state``.
            adb_version: ADB client version string.
            daemon: Daemon endpoint description (e.g. tcp:5037).
            connected_devices: Count or summary of connected devices.
            helper_note: Footnote under the metrics block.
        """
        if server_state is not None:
            self.set_server_state(server_state, text=server_state_text)
        elif server_state_text is not None:
            self.ui.status_row.set_value_text(server_state_text)
        if adb_version is not None:
            self.ui.version_row.set_value_text(adb_version)
        if daemon is not None:
            self.ui.daemon_row.set_value_text(daemon)
        if connected_devices is not None:
            self.ui.devices_row.set_value_text(connected_devices)
        if helper_note is not None:
            self.ui.helper_note.setText(helper_note)


class HostPanel(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Titles, tooltips, and placeholder copy for the host panel."""

        title: Final[str] = "Host device"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"
        identity_group_title: Final[str] = "Host identity"
        adb_group_title: Final[str] = "Android Debug Bridge"
        placeholder_host_name: str = field(default_factory=ui_faker.generate_host_name)
        placeholder_ip_address: str = field(
            default_factory=ui_faker.generate_private_ipv4
        )
        placeholder_platform: str = field(
            default_factory=ui_faker.generate_desktop_platform_label
        )
        placeholder_summary: str = field(
            default_factory=ui_faker.generate_host_identity_summary
        )
        placeholder_server_state_text: str = field(
            default_factory=ui_faker.generate_server_state_label
        )
        placeholder_adb_version: str = field(
            default_factory=ui_faker.generate_adb_version_string
        )
        placeholder_daemon: str = field(
            default_factory=ui_faker.generate_adb_daemon_endpoint
        )
        placeholder_connected_devices: str = field(
            default_factory=ui_faker.generate_connected_device_count_str
        )
        placeholder_helper_note: str = field(
            default_factory=ui_faker.generate_adb_bridge_helper_note
        )

    @dataclass
    class UI:
        """Composed widgets for host identity, ADB status, and panel chrome."""

        title: PanelTitle
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        host_identity: HostIdentitySection
        adb_bridge: AdbBridgeSection
        identity_group_box: GroupBox
        adb_group_box: GroupBox
        identity_indicator: ConditionIndicator
        adb_indicator: ConditionIndicator
        identity_wrapper: GridLayoutWrapper
        adb_wrapper: GridLayoutWrapper

    def __init__(self, parent=None):
        """Build the host panel with grouped identity and ADB sections.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: HostPanel.UI
        self.texts = HostPanel.Text()

        self._is_extended = False
        self._identity_os: Literal["linux", "windows", "darwin"] | None = "darwin"

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

        title = PanelTitle(
            parent=self,
            text=self.texts.title,
            icon_path=icon_qt_path(GenericIcons.LAPTOP),
        )

        expand_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_TOPBAR_INSET,
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

        host_identity = HostIdentitySection(self)
        identity_group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[host_identity],
            title=self.texts.identity_group_title,
        )
        identity_group_box.setObjectName("identity-group-box")

        identity_indicator = ConditionIndicator(
            self, object_name="host-identity-indicator"
        )
        identity_indicator.set_state("default")

        identity_wrapper = GridLayoutWrapper(
            self,
            spacing=Settings.SPACING.NONE,
            margins=Settings.HOST_PANEL.WRAPPER_MARGIN,
        )
        identity_wrapper.add_widget(identity_group_box, 0, 0)
        identity_wrapper.add_widget(
            identity_indicator,
            0,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        adb_bridge = AdbBridgeSection(self)
        adb_group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[adb_bridge],
            title=self.texts.adb_group_title,
        )
        adb_group_box.setObjectName("adb-group-box")

        adb_indicator = ConditionIndicator(self, object_name="adb-bridge-indicator")
        adb_indicator.set_state("default")

        adb_wrapper = GridLayoutWrapper(
            self,
            spacing=Settings.SPACING.NONE,
            margins=Settings.HOST_PANEL.WRAPPER_MARGIN,
        )
        adb_wrapper.add_widget(adb_group_box, 0, 0)
        adb_wrapper.add_widget(
            adb_indicator, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        adb_wrapper.setVisible(False)

        body = VerticalLayoutWrapper(
            self,
            widgets=[identity_wrapper, adb_wrapper],
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
            host_identity=host_identity,
            adb_bridge=adb_bridge,
            identity_group_box=identity_group_box,
            adb_group_box=adb_group_box,
            identity_indicator=identity_indicator,
            adb_indicator=adb_indicator,
            identity_wrapper=identity_wrapper,
            adb_wrapper=adb_wrapper,
        )

        self._finalize_ui_hooks()
        self._set_placeholder_values()

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
            self.ui.identity_wrapper, Qt.AlignmentFlag.AlignTop
        )
        self.ui.body.get_layout().setAlignment(
            self.ui.adb_wrapper, Qt.AlignmentFlag.AlignTop
        )
        self.layout().setAlignment(self.ui.body, Qt.AlignmentFlag.AlignTop)

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.identity_group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.adb_group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        # Preferred vertically so the panel can shrink when adb_wrapper is hidden;
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the host panel and its UI widgets."""
        #### Debugging signals ####
        view_signals.UiConstraintsDisabled.connect(self._on_ui_constraints_disabled)

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

    def _on_ui_constraints_disabled(self) -> None:
        """Handle the UI constraints disabled event."""
        self._set_placeholder_values()

    def _set_placeholder_values(self) -> None:
        """Populate placeholder values for the host identity and ADB bridge sections."""
        self._identity_os = "darwin"
        self.set_host_identity_values(
            host_name=self.texts.placeholder_host_name,
            summary=self.texts.placeholder_summary,
            ip_address=self.texts.placeholder_ip_address,
            platform=self.texts.placeholder_platform,
            os_icon=OperatingSystemIcons.MACOS,
            identity_state="valid",
        )
        self.set_adb_bridge_values(
            server_state="running",
            server_state_text=self.texts.placeholder_server_state_text.capitalize(),
            adb_version=self.texts.placeholder_adb_version,
            daemon=self.texts.placeholder_daemon,
            connected_devices=self.texts.placeholder_connected_devices,
            helper_note=self.texts.placeholder_helper_note,
            indicator_state="valid",
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
        self.ui.host_identity.set_host_values(
            host_name=host_name,
            summary=summary,
            ip_address=ip_address,
            platform=platform,
            os_icon=os_icon,
        )
        if identity_state is not None:
            self.ui.identity_indicator.set_state(identity_state)

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
        self.ui.adb_bridge.set_adb_values(
            server_state=server_state,
            server_state_text=server_state_text,
            adb_version=adb_version,
            daemon=daemon,
            connected_devices=connected_devices,
            helper_note=helper_note,
        )
        if indicator_state is not None:
            self.ui.adb_indicator.set_state(indicator_state)

    def _on_host_device_information_updated(
        self, name: str, os: Literal["linux", "windows", "darwin"] | None, ip: str
    ) -> None:
        """Handle the host device information updated."""
        assert os in ["linux", "windows", "darwin"]
        self._identity_os = os
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
            summary=self.texts.placeholder_summary,
            ip_address=ip,
            platform=os,
            os_icon=os_icon,
            identity_state="valid",
        )

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh header, host glyph, expand control, and ADB block icon for ``theme``."""
        self.ui.title.set_leading_icon_path(
            icon_qt_path_for_theme(theme, GenericIcons.LAPTOP)
        )
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_TOPBAR_INSET if inset else GenericIcons.LAYOUT_TOPBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.host_identity.ui.host_item.apply_theme_icons(theme)
        self.ui.adb_bridge.ui.android_svg.set_path(
            icon_qt_path_for_theme(theme, OperatingSystemIcons.ANDROID)
        )

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
            self.ui.adb_wrapper.setVisible(True)
            self.updateGeometry()

    def shorten_panel(self) -> None:
        """Shorten the host panel."""
        if self._is_extended:
            self._is_extended = False
            self.ui.adb_wrapper.setVisible(False)
            self.updateGeometry()
