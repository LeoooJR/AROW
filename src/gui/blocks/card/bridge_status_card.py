"""ADB bridge status card block."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui import faker as ui_faker
from gui.blocks.base import Block
from gui.blocks.card.card_settings import card_settings
from gui.colors import Theme
from gui.components import SVG, ConditionIndicator, GroupBox
from gui.components.media import get_svg_size
from gui.icons import OperatingSystemIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import GridLayoutWrapper

ADB_SERVER_STATE = Literal["running", "stopped", "starting", "error", "unknown"]


class AdbBridgeMetadataRow(QWidget):
    """Key/value row for ADB bridge metadata."""

    @dataclass(frozen=True)
    class Text:
        key: str = ""
        value: str = ""

    @dataclass
    class UI:
        key: QLabel
        value: QLabel

    def __init__(self, key_text: str, value_text: str, parent: QWidget | None = None):
        """Build an ADB bridge key/value metadata row."""
        super().__init__(parent)

        self.ui: AdbBridgeMetadataRow.UI
        self.texts = AdbBridgeMetadataRow.Text(key=key_text, value=value_text)
        self.setProperty("adb-bridge-metadata-row", True)

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(card_settings.KEY_VALUE_SPACING)

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
        """Run final setup hooks for the metadata row."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Set resize behavior for the row and its labels."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.key.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.value.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Align the key left and the value right within the row."""
        self.layout().setAlignment(
            self.ui.key, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.layout().setAlignment(
            self.ui.value, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def _connect_signals(self) -> None:
        """Connect row signals; metadata rows are static labels."""
        pass

    def set_key_text(self, text: str) -> None:
        """Update the row key label."""
        self.ui.key.setText(text)

    def set_value_text(self, text: str) -> None:
        """Update the row value label."""
        self.ui.value.setText(text)

    def set_value_state(self, state: str = "default") -> None:
        """Apply the ADB server-state styling token to the value label."""
        self.ui.value.setProperty("adb-server-state", state)
        self.ui.value.style().unpolish(self.ui.value)
        self.ui.value.style().polish(self.ui.value)
        self.ui.value.update()

    @property
    def value_label(self) -> QLabel:
        """Return the row value label."""
        return self.ui.value


class BridgeStatusContent(QFrame, Block):
    """Inner ADB bridge status content used by the grouped card block."""

    @dataclass(frozen=True)
    class Text:
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
        android_svg: SVG
        status_row: AdbBridgeMetadataRow
        version_row: AdbBridgeMetadataRow
        daemon_row: AdbBridgeMetadataRow
        devices_row: AdbBridgeMetadataRow
        helper_note: QLabel

    def __init__(self, parent: QWidget | None = None):
        """Build the inner ADB bridge status content with placeholder rows."""
        super().__init__(parent)

        self.ui: BridgeStatusContent.UI
        self.texts = BridgeStatusContent.Text()
        self.setObjectName("adb-bridge-section")
        self.setProperty("panel-section-compact", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(card_settings.ROW_SPACING)

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
        self.ui = BridgeStatusContent.UI(
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
        """Run final setup hooks for the ADB bridge content."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Set resize behavior for ADB bridge content rows."""
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
        """Center the Android icon and align helper text to the left."""
        self.layout().setAlignment(self.ui.android_svg, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.helper_note,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _connect_signals(self) -> None:
        """Connect content signals; ADB bridge content is updated by setters."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the Android icon for the active theme."""
        self.ui.android_svg.set_path(
            icon_qt_path_for_theme(theme, OperatingSystemIcons.ANDROID)
        )

    @property
    def status_row(self) -> AdbBridgeMetadataRow:
        """Return the ADB server-state metadata row."""
        return self.ui.status_row

    @property
    def version_row(self) -> AdbBridgeMetadataRow:
        """Return the ADB version metadata row."""
        return self.ui.version_row

    @property
    def daemon_row(self) -> AdbBridgeMetadataRow:
        """Return the daemon metadata row."""
        return self.ui.daemon_row

    @property
    def devices_row(self) -> AdbBridgeMetadataRow:
        """Return the connected-devices metadata row."""
        return self.ui.devices_row

    @property
    def helper_note(self) -> QLabel:
        """Return the ADB bridge helper note label."""
        return self.ui.helper_note

    def set_server_state(
        self, state: ADB_SERVER_STATE, text: str | None = None
    ) -> None:
        """Update the server-state row text and styling state."""
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
        """Update displayed ADB bridge values, leaving omitted fields unchanged."""
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


class BridgeStatusCardBlock(QFrame, Block):
    """Grouped ADB bridge card with status indicator."""

    @dataclass(frozen=True)
    class Text:
        """Title and placeholder values owned by the ADB bridge card block."""

        title: Final[str] = "Android Debug Bridge"
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
        content: BridgeStatusContent
        group_box: GroupBox
        indicator: ConditionIndicator
        wrapper: GridLayoutWrapper

    def __init__(self, parent: QWidget | None = None):
        """Build the grouped ADB bridge card with its status indicator."""
        super().__init__(parent)
        self.texts = BridgeStatusCardBlock.Text()

        content = BridgeStatusContent(self)
        group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[content],
            title=self.texts.title,
        )
        group_box.setObjectName("adb-group-box")

        indicator = ConditionIndicator(self, object_name="adb-bridge-indicator")
        indicator.set_state("default")

        wrapper = GridLayoutWrapper(
            self,
            spacing=Settings.SPACING.NONE,
            margins=card_settings.WRAPPER_MARGIN,
        )
        wrapper.add_widget(group_box, 0, 0)
        wrapper.add_widget(
            indicator, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.SPACING.NONE)
        layout.addWidget(wrapper)
        self.setLayout(layout)

        self.ui = BridgeStatusCardBlock.UI(
            content=content,
            group_box=group_box,
            indicator=indicator,
            wrapper=wrapper,
        )
        self._finalize_ui_hooks()
        self.set_placeholder_values()

    def _set_size_policy(self) -> None:
        """Set resize behavior for the ADB bridge card group box."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Keep the ADB bridge card wrapper anchored to the top."""
        self.layout().setAlignment(self.ui.wrapper, Qt.AlignmentFlag.AlignTop)

    def _connect_signals(self) -> None:
        """Connect card signals; placeholder/debug values are block-owned."""
        signals.UI.UiConstraintsDisabled.connect(self._on_ui_constraints_disabled)
        signals.ADB_SERVER.ADBServerStarted.connect(self._on_adb_server_started)
        signals.ADB_SERVER.ADBServerStopped.connect(self._on_adb_server_stopped)

    ### Slots ###

    @Slot()
    def _on_adb_server_started(self) -> None:
        """Update bridge card when the ADB server starts."""
        self.set_adb_values(server_state="running", indicator_state="valid")

    @Slot()
    def _on_adb_server_stopped(self) -> None:
        """Update bridge card when the ADB server stops."""
        self.set_adb_values(server_state="stopped", indicator_state="error")

    @Slot()
    def _on_ui_constraints_disabled(self) -> None:
        """Re-apply placeholder values when UI constraints are disabled."""
        self.set_placeholder_values()

    def set_placeholder_values(self) -> None:
        """Populate the card with generated placeholder ADB bridge values."""
        self.set_adb_values(
            server_state="running",
            server_state_text=self.texts.placeholder_server_state_text.capitalize(),
            adb_version=self.texts.placeholder_adb_version,
            daemon=self.texts.placeholder_daemon,
            connected_devices=self.texts.placeholder_connected_devices,
            helper_note=self.texts.placeholder_helper_note,
            indicator_state="valid",
        )

    def set_adb_values(
        self,
        server_state: ADB_SERVER_STATE | None = None,
        server_state_text: str | None = None,
        adb_version: str | None = None,
        daemon: str | None = None,
        connected_devices: str | None = None,
        helper_note: str | None = None,
        indicator_state: str | None = None,
    ) -> None:
        """Update ADB bridge content and optional indicator state."""
        self.ui.content.set_adb_values(
            server_state=server_state,
            server_state_text=server_state_text,
            adb_version=adb_version,
            daemon=daemon,
            connected_devices=connected_devices,
            helper_note=helper_note,
        )
        if indicator_state is not None:
            self.ui.indicator.set_state(indicator_state)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh theme-dependent icons inside the ADB bridge card."""
        self.ui.content.apply_theme_icons(theme)

    @property
    def content(self) -> BridgeStatusContent:
        """Return the ADB bridge card content widget."""
        return self.ui.content

    @property
    def indicator(self) -> ConditionIndicator:
        """Return the ADB bridge state indicator."""
        return self.ui.indicator


AdbBridgeMetadataRowBlock = AdbBridgeMetadataRow
AdbBridgeSection = BridgeStatusContent


__all__ = [
    "ADB_SERVER_STATE",
    "AdbBridgeMetadataRow",
    "AdbBridgeMetadataRowBlock",
    "AdbBridgeSection",
    "BridgeStatusCardBlock",
    "BridgeStatusContent",
]
