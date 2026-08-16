"""Host identity card block."""

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
from gui.components import ConditionIndicator, GroupBox, LeadingIconLabel
from gui.constants.colors import Theme
from gui.constants.icons import ApplicationIcons, GenericIcons, OperatingSystemIcons
from gui.constants.settings import Settings
from gui.signals import signals
from gui.wrapper import GridLayoutWrapper


class HostIdentityMetadataRow(QWidget):
    """Key/value row for host identity metadata."""

    @dataclass(frozen=True)
    class Text:
        key: str = ""
        value: str = ""

    @dataclass
    class UI:
        key: QLabel
        value: QLabel

    def __init__(self, key_text: str, value_text: str, parent: QWidget | None = None):
        """Build a host identity key/value metadata row."""
        super().__init__(parent)

        self.ui: HostIdentityMetadataRow.UI
        self.texts = HostIdentityMetadataRow.Text(key=key_text, value=value_text)
        self.setProperty("host-identity-metadata-row", True)

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
        self.ui = HostIdentityMetadataRow.UI(key=key, value=value)
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

    @property
    def value_label(self) -> QLabel:
        """Return the row value label."""
        return self.ui.value


class IdentityCardContent(QFrame, Block):
    """Inner host identity content used by the grouped card block."""

    @dataclass(frozen=True)
    class Text:
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
        host_name: QLabel
        host_summary: QLabel
        host_item: LeadingIconLabel
        ip_address_row: HostIdentityMetadataRow
        platform_row: HostIdentityMetadataRow

    def __init__(self, parent: QWidget | None = None):
        """Build the inner host identity content with placeholder fields."""
        super().__init__(parent)

        self.ui: IdentityCardContent.UI
        self.texts = IdentityCardContent.Text()
        self.setObjectName("host-identity-section")
        self.setProperty("panel-section-compact", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(card_settings.ROW_SPACING)

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
        self.ui = IdentityCardContent.UI(
            host_name=host_name,
            host_summary=host_summary,
            host_item=host_item,
            ip_address_row=ip_address_row,
            platform_row=platform_row,
        )
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run final setup hooks for the host identity content."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Set resize behavior for host identity content rows."""
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
        """Align the host title row and supporting summary text."""
        self.layout().setAlignment(self.ui.host_item, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.host_summary,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

    def _connect_signals(self) -> None:
        """Connect content signals; host identity content is updated by setters."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the operating-system icon used by the host title row."""
        self.ui.host_item.apply_theme_icons(theme)

    @property
    def host_name_label(self) -> QLabel:
        """Return the host name label."""
        return self.ui.host_name

    @property
    def host_summary_label(self) -> QLabel:
        """Return the host summary label."""
        return self.ui.host_summary

    @property
    def ip_address_row(self) -> HostIdentityMetadataRow:
        """Return the local IP metadata row."""
        return self.ui.ip_address_row

    @property
    def platform_row(self) -> HostIdentityMetadataRow:
        """Return the platform metadata row."""
        return self.ui.platform_row

    def set_host_values(
        self,
        host_name: str | None = None,
        summary: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        os_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
    ) -> None:
        """Update displayed host identity values, leaving omitted fields unchanged."""
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


class IdentityCardBlock(QFrame, Block):
    """Grouped host identity card with status indicator."""

    @dataclass(frozen=True)
    class Text:
        """Title and placeholder values owned by the identity card block."""

        title: Final[str] = "Host identity"
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

    @dataclass
    class UI:
        content: IdentityCardContent
        group_box: GroupBox
        indicator: ConditionIndicator
        wrapper: GridLayoutWrapper

    def __init__(self, parent: QWidget | None = None):
        """Build the grouped host identity card with its status indicator."""
        super().__init__(parent)
        self.texts = IdentityCardBlock.Text()

        content = IdentityCardContent(self)
        group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[content],
            title=self.texts.title,
        )
        group_box.setObjectName("identity-group-box")

        indicator = ConditionIndicator(self, object_name="host-identity-indicator")
        indicator.set_state("default")

        wrapper = GridLayoutWrapper(
            self,
            spacing=Settings.SPACING.NONE,
            margins=card_settings.WRAPPER_MARGIN,
        )
        wrapper.add_widget(group_box, 0, 0)
        wrapper.add_widget(
            indicator,
            0,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.SPACING.NONE)
        layout.addWidget(wrapper)
        self.setLayout(layout)

        self.ui = IdentityCardBlock.UI(
            content=content,
            group_box=group_box,
            indicator=indicator,
            wrapper=wrapper,
        )
        self._finalize_ui_hooks()
        self.set_placeholder_values()

    def _set_size_policy(self) -> None:
        """Set resize behavior for the host identity card group box."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Keep the identity card wrapper anchored to the top."""
        self.layout().setAlignment(self.ui.wrapper, Qt.AlignmentFlag.AlignTop)

    def _connect_signals(self) -> None:
        """Connect card signals."""
        signals.HOST.HostDeviceInformationUpdated.connect(
            self._on_host_device_information_updated
        )

    ### Slots ###

    @Slot(str, str, str)
    def _on_host_device_information_updated(
        self, name: str, os: Literal["linux", "windows", "darwin"] | None, ip: str
    ) -> None:
        """Update host identity when controller reports host device metadata."""
        if os is not None and os not in ("linux", "windows", "darwin"):
            raise ValueError(f"Unsupported host OS: {os!r}")
        os_icon: GenericIcons | OperatingSystemIcons
        if os == "linux":
            os_icon = OperatingSystemIcons.LINUX
        elif os == "windows":
            os_icon = OperatingSystemIcons.WINDOWS
        elif os == "darwin":
            os_icon = OperatingSystemIcons.MACOS
        else:
            os_icon = GenericIcons.LAPTOP
        self.set_host_values(
            host_name=name,
            ip_address=ip,
            platform=os,
            os_icon=os_icon,
            identity_state="valid",
        )

    def set_placeholder_values(self) -> None:
        """Populate the card with generated placeholder host identity values."""
        self.set_host_values(
            host_name=self.texts.placeholder_host_name,
            summary=self.texts.placeholder_summary,
            ip_address=self.texts.placeholder_ip_address,
            platform=self.texts.placeholder_platform,
            os_icon=OperatingSystemIcons.MACOS,
            identity_state="valid",
        )

    def set_host_values(
        self,
        host_name: str | None = None,
        summary: str | None = None,
        ip_address: str | None = None,
        platform: str | None = None,
        os_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
        identity_state: str | None = None,
    ) -> None:
        """Update host identity content and optional indicator state."""
        self.ui.content.set_host_values(
            host_name=host_name,
            summary=summary,
            ip_address=ip_address,
            platform=platform,
            os_icon=os_icon,
        )
        if identity_state is not None:
            self.ui.indicator.set_state(identity_state)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh theme-dependent icons inside the identity card."""
        self.ui.content.apply_theme_icons(theme)

    @property
    def content(self) -> IdentityCardContent:
        """Return the identity card content widget."""
        return self.ui.content

    @property
    def indicator(self) -> ConditionIndicator:
        """Return the identity card state indicator."""
        return self.ui.indicator


HostIdentityMetadataRowBlock = HostIdentityMetadataRow
HostIdentitySection = IdentityCardContent


__all__ = [
    "HostIdentityMetadataRow",
    "HostIdentityMetadataRowBlock",
    "HostIdentitySection",
    "IdentityCardBlock",
    "IdentityCardContent",
]
