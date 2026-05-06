"""
This file contains all graphical elements related to the device panel.
"""

from dataclasses import dataclass, field
from typing import Final, Literal, Optional

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui import faker as ui_faker
from gui.animation import (
    animate_widget_visibility,
    apply_highlight_level,
    compute_sine_pulse_level,
)
from gui.elements import GroupBox, HelperText, List, PanelTitle, PlaceHolder, ToolButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import (
    GridLayoutWrapper,
    HorizontalLayoutWrapper,
    VerticalLayoutWrapper,
)
from logger import logger

DeviceKind = Literal["mobile"]
DeviceBadge = Literal["none", "active", "trusted", "new"]


class _DeviceItemRowWidget(QWidget):
    """Keeps the host `QListWidgetItem` height in sync when wrapped labels reflow on resize."""

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the device row widget."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the device row widget."""

        pass

    def __init__(self, device_item: "DeviceItem"):
        """Attach resize tracking to a device list item row.

        Args:
            device_item: Owning list item whose size hint should stay in sync.
        """
        super().__init__()
        self.texts = _DeviceItemRowWidget.Text()
        self.ui = _DeviceItemRowWidget.UI()
        self._device_item = device_item

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._device_item._sync_size_hint()


class DeviceItem(QListWidgetItem):
    """
    Rich list entry: lead icon, title + badges, subtitle (OS / location),
    last-communication label, and a menu affordance. The visual row is a QWidget
    attached via setItemWidget after the item is added to a QListWidget.
    """

    _ICON_INNER_PX: int = 24
    _SUBTITLE_ICON_PX: int = 14

    @dataclass(frozen=True)
    class Text:
        """Default labels, badges, and affordances for a device list row."""

        default_name: Final[str] = "Unknown Device"
        menu_button: Final[str] = "⋮"
        menu_button_tooltip: Final[str] = "Device actions"
        active_badge: Final[str] = "Active"
        trusted_badge: Final[str] = "Trusted"
        new_badge: Final[str] = "New"
        empty_subtitle: Final[str] = "—"

    @dataclass
    class UI:
        """Widgets that render the rich device list row."""

        row: QWidget
        main_row: HorizontalLayoutWrapper
        icon_frame: HorizontalLayoutWrapper
        center: VerticalLayoutWrapper
        right_wrap: HorizontalLayoutWrapper
        title_row: HorizontalLayoutWrapper
        name_label: QLabel
        badge_container: HorizontalLayoutWrapper
        subtitle_host: VerticalLayoutWrapper
        subtitle_label: QLabel
        time_label: QLabel
        menu_button: QToolButton
        icon_label: QLabel
        helper_text: str

    def __init__(
        self,
        parent=None,
        text: str | None = None,
        type: str = "available",
        *,
        device_kind: DeviceKind = "mobile",
        badge: DeviceBadge = "none",
        operating_system: str = "",
        location: str = "",
        last_communication: str = "",
        alert_highlight: bool = False,
    ):
        """Create a styled device entry for embedding in a ``QListWidget``.

        Args:
            parent: Optional list widget or owner passed to ``QListWidgetItem``.
            text: Primary device name; falls back to default when omitted.
            type: Device category label used in helper/status copy.
            device_kind: Fixed literal for supported device kinds (currently mobile).
            badge: Visual trust/activity badge variant.
            operating_system: OS line shown in the subtitle stack.
            location: Location line shown in the subtitle stack.
            last_communication: Right-side recency label when extended.
            alert_highlight: When True, apply attention styling to the row.
        """
        super().__init__(parent)

        self.texts = DeviceItem.Text()

        display_name = text if text is not None else self.texts.default_name
        helper_text = f"{type.capitalize()} device"

        self.setToolTip(display_name)
        self.setStatusTip(helper_text)
        self.setWhatsThis(helper_text)

        self.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.setIcon(QIcon())

        self._text: str = display_name
        self._device_kind: DeviceKind = device_kind
        self._badge: DeviceBadge = badge
        self._operating_system: str = operating_system
        self._location: str = location
        self._last_communication: str = last_communication
        self._alert_highlight: bool = alert_highlight
        self._is_extended: bool = False
        self._sync_size_hint_in_progress: bool = False

        row = _DeviceItemRowWidget(self)
        row.setObjectName("device-item-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        icon_path = GenericIcons.DEVICE.value
        icon_label = QLabel(row)
        icon_label.setPixmap(
            QIcon(icon_path).pixmap(QSize(self._ICON_INNER_PX, self._ICON_INNER_PX))
        )
        icon_label.setFixedSize(self._ICON_INNER_PX, self._ICON_INNER_PX)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_frame = HorizontalLayoutWrapper(
            row,
            widgets=[icon_label],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        icon_frame.setObjectName("device-item-icon-frame")
        icon_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        name_label = QLabel(display_name, row)
        name_label.setObjectName("device-item-name")
        name_label.setFont(
            QFont(
                Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.DemiBold
            )
        )
        DeviceItem._configure_wrapped_line_label(
            name_label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        badge_container = HorizontalLayoutWrapper(
            row,
            widgets=[],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        badge_container.setObjectName("device-item-badge-container")
        badge_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        subtitle_label = QLabel(row)
        subtitle_label.setObjectName("device-item-subtitle")
        subtitle_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        DeviceItem._configure_wrapped_line_label(
            subtitle_label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        subtitle_host = VerticalLayoutWrapper(
            row,
            widgets=[subtitle_label],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        subtitle_host.setObjectName("device-item-subtitle-host")
        subtitle_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        time_label = QLabel(row)
        time_label.setObjectName("device-item-time")
        time_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        DeviceItem._configure_wrapped_line_label(
            time_label, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )

        menu_button = QToolButton(row)
        menu_button.setObjectName("device-item-menu")
        menu_button.setText(self.texts.menu_button)
        menu_button.setToolTip(self.texts.menu_button_tooltip)
        menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        menu_button.setAutoRaise(True)
        menu_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        title_row = HorizontalLayoutWrapper(
            row,
            widgets=[name_label, badge_container],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_NAME_BADGE_GAP,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_end=True,
        )
        title_row.setObjectName("device-item-title-row")
        title_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        center = VerticalLayoutWrapper(
            row,
            widgets=[title_row, subtitle_host],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_TITLE_SUBTITLE_SPACING,
            margins=(
                0,
                Settings.LIST.DEVICE_ITEM_CENTER_PADDING_V,
                0,
                Settings.LIST.DEVICE_ITEM_CENTER_PADDING_V,
            ),
        )
        center.setObjectName("device-item-center")
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        right_wrap = HorizontalLayoutWrapper(
            row,
            widgets=[time_label, menu_button],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_RIGHT_GAP,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        right_wrap.setObjectName("device-item-right-wrap")
        right_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        right_wrap.hide()

        main_row = HorizontalLayoutWrapper(
            row,
            widgets=[icon_frame, center, right_wrap],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_ICON_GAP,
            margins=(
                Settings.LIST.DEVICE_ITEM_ROW_PADDING_H,
                Settings.LIST.DEVICE_ITEM_ROW_PADDING_V,
                Settings.LIST.DEVICE_ITEM_ROW_PADDING_H,
                Settings.LIST.DEVICE_ITEM_ROW_PADDING_V,
            ),
        )
        main_row.get_layout().setStretchFactor(center, 1)
        main_row.get_layout().setAlignment(icon_frame, Qt.AlignmentFlag.AlignCenter)

        row_layout = QVBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(main_row)
        row.setLayout(row_layout)

        self.ui: DeviceItem.UI = DeviceItem.UI(
            row=row,
            main_row=main_row,
            icon_frame=icon_frame,
            center=center,
            right_wrap=right_wrap,
            title_row=title_row,
            name_label=name_label,
            badge_container=badge_container,
            subtitle_host=subtitle_host,
            subtitle_label=subtitle_label,
            time_label=time_label,
            menu_button=menu_button,
            icon_label=icon_label,
            helper_text=helper_text,
        )

        self._apply_badge()
        self._refresh_subtitle()
        self.set_last_communication(last_communication)
        self.set_alert_highlight(alert_highlight)
        self._finalize_ui_hooks()
        self._sync_size_hint()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the device item."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    @staticmethod
    def _configure_wrapped_line_label(
        label: QLabel, alignment: Qt.AlignmentFlag
    ) -> None:
        """Multiline-capable label: no elision; text reflows within the list item width."""
        label.setWordWrap(True)
        label.setAlignment(alignment)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        label.setMinimumWidth(0)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def _set_size_policy(self) -> None:
        """Size policies for the row and its regions (icon / center text / right actions)."""
        self.ui.row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.ui.icon_frame.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.center.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        self.ui.right_wrap.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self.ui.name_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.badge_container.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        self.ui.subtitle_host.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.subtitle_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.time_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.menu_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.title_row.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Layout alignment: icon vertically centered in the row; text column anchored for readable spacing."""
        self.ui.main_row.get_layout().setAlignment(
            self.ui.icon_frame, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.title_row.get_layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ui.center.get_layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.ui.right_wrap.get_layout().setAlignment(
            self.ui.menu_button, Qt.AlignmentFlag.AlignVCenter
        )
        self.ui.right_wrap.get_layout().setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def _connect_signals(self) -> None:
        """Signals for the device row (menu, future actions)."""
        pass

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _sync_size_hint(self) -> None:
        if self._sync_size_hint_in_progress:
            return
        try:
            self._sync_size_hint_in_progress = True
            row = self.ui.row
            lay = row.layout()
            if lay is not None:
                lay.invalidate()
                lay.activate()
            row.updateGeometry()

            # Extended: keep current behavior (size hint tracks the laid-out row).
            if self._is_extended:
                sh = row.sizeHint()
                h = max(Settings.LIST.DEVICE_ITEM_ROW_MIN_HEIGHT, sh.height())
                self.setSizeHint(QSize(sh.width(), h))
            else:
                # Shortened: do not carry over the row's stretched width from the extended
                # state — width must match hidden right column so AdjustToContents can shrink.
                mw = max(1, row.minimumSizeHint().width())
                saved = QSize(row.width(), row.height())
                row.resize(mw, saved.height())
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                sh = row.sizeHint()
                row.resize(saved)
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                h = max(Settings.LIST.DEVICE_ITEM_ROW_MIN_HEIGHT, sh.height())
                self.setSizeHint(QSize(mw, h))
        finally:
            self._sync_size_hint_in_progress = False
        lw = self.listWidget()
        if lw is not None:
            lw.viewport().update()

    def _apply_badge(self) -> None:
        layout = self.ui.badge_container.layout()
        assert layout is not None
        self._clear_layout(layout)
        if self._badge == "none":
            return
        if self._badge == "active":
            lab = QLabel(self.texts.active_badge)
            lab.setProperty("device-item-badge", "active")
            lab.setFont(
                QFont(
                    Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal
                )
            )
            lab.setWordWrap(True)
            lab.setMinimumWidth(0)
            lab.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            layout.addWidget(lab)
        elif self._badge == "trusted":
            ic = QLabel()
            ic.setPixmap(
                QIcon(GenericIcons.CHECK.value).pixmap(
                    QSize(self._SUBTITLE_ICON_PX, self._SUBTITLE_ICON_PX)
                )
            )
            tx = QLabel(self.texts.trusted_badge)
            tx.setProperty("device-item-badge", "trusted-text")
            tx.setFont(
                QFont(
                    Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal
                )
            )
            tx.setWordWrap(True)
            tx.setMinimumWidth(0)
            tx.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            layout.addWidget(ic)
            layout.addWidget(tx)
        elif self._badge == "new":
            lab = QLabel(self.texts.new_badge)
            lab.setProperty("device-item-badge", "new")
            lab.setFont(
                QFont(
                    Settings.FONT.FAMILY,
                    Settings.FONT.SIZE_HELPER,
                    QFont.Weight.DemiBold,
                )
            )
            lab.setWordWrap(True)
            lab.setMinimumWidth(0)
            lab.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            layout.addWidget(lab)
        layout.addStretch(1)

    def _refresh_subtitle(self) -> None:
        chunks: list[str] = []
        if self._operating_system:
            chunks.append(self._operating_system)
        if self._location:
            chunks.append(self._location)
        self.ui.subtitle_label.setText(
            " · ".join(chunks) if chunks else self.texts.empty_subtitle
        )

    def get_text(self) -> str:
        return self.ui.name_label.text().strip()

    def set_text(self, text: str) -> None:
        self.ui.name_label.setText(text)
        self._sync_size_hint()

    def set_operating_system(self, text: str) -> None:
        self._operating_system = text
        self._refresh_subtitle()
        self._sync_size_hint()

    def set_location(self, text: str) -> None:
        self._location = text
        self._refresh_subtitle()
        self._sync_size_hint()

    def set_last_communication(self, text: str) -> None:
        self._last_communication = text
        self.ui.time_label.setText(text)
        self._sync_size_hint()

    def set_alert_highlight(self, enabled: bool) -> None:
        self._alert_highlight = enabled
        self.ui.row.setProperty("alert", enabled)
        self.ui.row.style().unpolish(self.ui.row)
        self.ui.row.style().polish(self.ui.row)
        self.ui.row.update()

    def set_badge(self, badge: DeviceBadge) -> None:
        self._badge = badge
        self._apply_badge()
        self._sync_size_hint()

    def set_device_kind(self, kind: DeviceKind) -> None:
        self._device_kind = kind
        path = GenericIcons.DEVICE.value
        self.ui.icon_label.setPixmap(
            QIcon(path).pixmap(QSize(self._ICON_INNER_PX, self._ICON_INNER_PX))
        )

    @classmethod
    def add_to_list(
        cls,
        list_widget: QListWidget,
        *,
        text: str | None = None,
        type: str = "available",
        device_kind: DeviceKind = "mobile",
        badge: DeviceBadge = "none",
        operating_system: str = "",
        location: str = "",
        last_communication: str = "",
        alert_highlight: bool = False,
    ) -> "DeviceItem":
        item = cls(
            None,
            text=text,
            type=type,
            device_kind=device_kind,
            badge=badge,
            operating_system=operating_system,
            location=location,
            last_communication=last_communication,
            alert_highlight=alert_highlight,
        )
        list_widget.addItem(item)
        list_widget.setItemWidget(item, item.ui.row)
        QTimer.singleShot(0, item._sync_size_hint)
        return item

    def extend_device_item(self) -> None:
        """Extend the device item to show the last communication time and menu button."""
        if self._is_extended:
            return
        self._is_extended = True
        self.ui.right_wrap.show()
        self._sync_size_hint()

    def shorten_device_item(self) -> None:
        """Shorten the device item to hide the last communication time and menu button."""
        if not self._is_extended:
            return
        self._is_extended = False
        self.ui.right_wrap.hide()
        self._sync_size_hint()


class DeviceState(QGroupBox):

    @dataclass(frozen=True)
    class Text:
        """Template strings for the device state summary group."""

        title: Final[str] = "About device"
        state: Final[str] = "State: <state>"
        operating_system: Final[str] = "Operating system: <operating_system>"
        last_communication: Final[str] = "Last communication: <last_communication>"

    @dataclass
    class UI:
        """State lines inside the about-device group box."""

        state: QLabel
        operating_system: QLabel
        last_communication: QLabel

    def __init__(self, parent=None):
        """Build the grouped device state labels.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = DeviceState.Text()
        super().__init__(
            parent, title=self.texts.title, alignment=Qt.AlignmentFlag.AlignLeft
        )

        self.ui: DeviceState.UI

        self.setProperty("panel-section", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Padding handled by panel-section style
        layout.setSpacing(8)  # Spacing between state items

        state = QLabel(self.texts.state, self)
        state.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )
        layout.addWidget(state)

        operating_system = QLabel(self.texts.operating_system, self)
        operating_system.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )
        layout.addWidget(operating_system)

        last_communication = QLabel(self.texts.last_communication, self)
        last_communication.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )
        layout.addWidget(last_communication)

        self.setLayout(layout)

        self.ui: DeviceState.UI = DeviceState.UI(
            state=state,
            operating_system=operating_system,
            last_communication=last_communication,
        )
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the device state section."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Centralize size policies for the device state section."""
        self.ui.state.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.operating_system.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.last_communication.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Centralize alignment for the device state section."""
        self.ui.state.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.ui.operating_system.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.ui.last_communication.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

    def _connect_signals(self) -> None:
        """Connect signals for the device state section."""
        pass


class DevicePairingPanel(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Copy for the device pairing side panel."""

        title: Final[str] = "Pairing Device"

    @dataclass
    class UI:
        """Chrome and body regions for pairing-specific content."""

        title: PanelTitle
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

        title = PanelTitle(
            parent=None, text=self.texts.title, icon_path=GenericIcons.DEVICE.value
        )
        title.setProperty("main-panel-title", True)

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
        """Titles, tooltips, empty states, and placeholder device copy."""

        title: Final[str] = "Linked Devices"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"
        empty_state: Final[str] = "No device found"
        add_device_tooltip: Final[str] = "Add a device"
        refresh_button_tooltip: Final[str] = "Refresh device list"
        trash_button_tooltip: Final[str] = "Remove all devices"
        select_helper_text: Final[str] = "Select a device to work with"
        available_devices_group_title: Final[str] = "Available devices"
        placeholder_primary_device: str = field(
            default_factory=ui_faker.generate_android_device_model
        )
        placeholder_secondary_device: str = field(
            default_factory=ui_faker.generate_android_device_model
        )
        placeholder_unknown_device: Final[str] = "Unknown Device"
        placeholder_operating_system: str = field(
            default_factory=ui_faker.generate_android_release_label
        )
        placeholder_location_primary: str = field(
            default_factory=ui_faker.generate_city_state_location
        )
        placeholder_location_secondary: str = field(
            default_factory=ui_faker.generate_city_state_location
        )
        placeholder_last_communication_active: Final[str] = "Active now"
        placeholder_last_communication_recent: Final[str] = "30 min ago"
        placeholder_last_communication_old: Final[str] = "2 hours ago"

    @dataclass
    class UI:
        """Full device selection UI: list, actions, helper text, and state box."""

        title: PanelTitle
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        available_device_list: List
        available_device_empty_state: PlaceHolder
        available_device_wrapper: HorizontalLayoutWrapper
        available_device_group_box: GroupBox
        add_device_button: ToolButton
        refresh_button: ToolButton
        trash_button: ToolButton
        buttons_wrapper: GridLayoutWrapper
        select_helper_text: HelperText
        device_state: DeviceState

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

        title = PanelTitle(
            parent=self, text=self.texts.title, icon_path=GenericIcons.DEVICE.value
        )

        expand_button = ToolButton(
            self,
            icon_path=GenericIcons.LAYOUT_TOPBAR_INSET.value,
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

        available_device_list = List(None)
        available_device_list.setObjectName("availabe-device-list")
        available_device_empty_state = PlaceHolder(
            available_device_list.viewport(),
            text=self.texts.empty_state,
            minimum_width=0,
            minimum_height=0,
            icon_path=GenericIcons.DEVICE_PLACEHOLDER.value,
        )
        available_device_empty_state.setObjectName("available-device-empty-state")
        available_device_empty_state.setProperty("place-holder", False)
        available_device_empty_state.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, False
        )
        available_device_empty_state.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        available_device_empty_state.ui.text.setWordWrap(True)
        available_device_empty_state.ui.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        available_device_empty_state.style().unpolish(available_device_empty_state)
        available_device_empty_state.style().polish(available_device_empty_state)
        available_device_empty_state.hide()

        add_device_button = ToolButton(
            self,
            icon_path=GenericIcons.PLUS.value,
            tooltip=self.texts.add_device_tooltip,
        )
        add_device_button.setEnabled(True)
        add_device_button.setObjectName("add-device-button")

        refresh_button = ToolButton(
            self,
            icon_path=GenericIcons.ARROW_CLOCKWISE.value,
            tooltip=self.texts.refresh_button_tooltip,
        )
        refresh_button.setEnabled(True)
        refresh_button.setObjectName("refresh-button")

        trash_button = ToolButton(
            self,
            icon_path=GenericIcons.TRASH.value,
            tooltip=self.texts.trash_button_tooltip,
        )
        trash_button.setEnabled(True)
        trash_button.setObjectName("trash-button")

        buttons_wrapper = GridLayoutWrapper(
            self,
            widgets=[
                (add_device_button, 0, 0),
                (refresh_button, 0, 1),
                (trash_button, 1, 0),
            ],
        )

        available_device_wrapper = HorizontalLayoutWrapper(
            self, widgets=[available_device_list, buttons_wrapper]
        )
        available_device_wrapper.get_layout().setStretchFactor(available_device_list, 1)
        available_device_wrapper.get_layout().setStretchFactor(buttons_wrapper, 0)

        select_helper_text = HelperText(self, self.texts.select_helper_text)

        available_device_group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[available_device_wrapper, select_helper_text],
            title=self.texts.available_devices_group_title,
        )

        body = VerticalLayoutWrapper(
            self,
            widgets=[available_device_group_box],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        body.get_layout().setStretchFactor(available_device_group_box, 1)
        layout.addWidget(body, 1)

        device_state = DeviceState(self)
        device_state.setObjectName("device-state")
        device_state.setVisible(False)
        layout.addWidget(device_state)

        self.setLayout(layout)

        self.ui: DeviceSelectionPanel.UI = DeviceSelectionPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            available_device_list=available_device_list,
            available_device_empty_state=available_device_empty_state,
            available_device_group_box=available_device_group_box,
            available_device_wrapper=available_device_wrapper,
            add_device_button=add_device_button,
            refresh_button=refresh_button,
            trash_button=trash_button,
            buttons_wrapper=buttons_wrapper,
            select_helper_text=select_helper_text,
            device_state=device_state,
        )

        available_device_list.viewport().installEventFilter(self)

        # Timers for attention highlight: smooth pulse (sine-driven level 0–10)
        self._highlight_pulse_timer = QTimer(self)
        self._highlight_pulse_timer.setSingleShot(False)
        self._highlight_pulse_timer.timeout.connect(self._on_highlight_pulse_tick)
        self._highlight_stop_timer = QTimer(self)
        self._highlight_stop_timer.setSingleShot(True)
        self._highlight_stop_timer.timeout.connect(self.stop_highlight_attention)
        self._highlight_elapsed = QElapsedTimer()

        self._finalize_ui_hooks()
        self._update_available_device_empty_state_visibility()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the device selection panel."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.ui.available_device_list.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._reposition_available_device_empty_state()
        return super().eventFilter(watched, event)

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.ui.available_device_group_box.layout().setAlignment(
            self.ui.select_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.available_device_wrapper.get_layout().setAlignment(
            self.ui.buttons_wrapper,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.available_device_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.available_device_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.available_device_group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.select_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.device_state.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the device selection panel and its UI widgets."""

        #### Debugging signals ####
        view_signals.UiConstraintsDisabled.connect(self._on_ui_constraints_disabled)

        #### Signals for selecting a device workflow (pairing, selection, connection) ####
        self.ui.add_device_button.clicked.connect(view_signals.AddDeviceRequested.emit)
        view_signals.AuthentificationSucceeded.connect(
            self._on_authentification_succeeded
        )
        self.ui.available_device_list.itemClicked.connect(self._on_device_selected)
        view_signals.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        view_signals.DevicesUpdated.connect(self._on_devices_updated)
        self.ui.refresh_button.clicked.connect(self._on_refresh_button_clicked)
        self.ui.trash_button.clicked.connect(self._on_trash_button_clicked)

        #### Signals for toggling the device selection panel visibility ####
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: view_signals.DeviceSelectionPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

        #### Keep in-list placeholder visibility synchronized with list model ####
        model = self.ui.available_device_list.model()
        model.rowsInserted.connect(self._on_available_device_list_model_changed)
        model.rowsRemoved.connect(self._on_available_device_list_model_changed)
        model.modelReset.connect(self._on_available_device_list_model_changed)
        model.layoutChanged.connect(self._on_available_device_list_model_changed)
        model.dataChanged.connect(self._on_available_device_list_model_changed)

    def _reposition_available_device_empty_state(self) -> None:
        """Keep empty-state placeholder centered inside the list viewport."""
        viewport = self.ui.available_device_list.viewport()
        placeholder = self.ui.available_device_empty_state

        # Fill most of the viewport to avoid text/icon clipping on narrow panel widths.
        inset = Settings.SPACING.XS
        geometry = viewport.rect().adjusted(inset, inset, -inset, -inset)
        placeholder.setGeometry(geometry)

        # Adapt icon size to available room so it never collides with the label.
        min_side = max(0, min(geometry.width(), geometry.height()))
        icon_size = max(24, min(Settings.PLACEHOLDER.ICON_SIZE, int(min_side * 0.38)))
        placeholder.ui.icon.setFixedSize(icon_size, icon_size)
        placeholder.raise_()

    def _update_available_device_empty_state_visibility(self) -> None:
        """Show empty-state content in-list when no device is available."""
        is_empty = self.ui.available_device_list.count() == 0
        self.ui.available_device_empty_state.setVisible(is_empty)
        if is_empty:
            self._reposition_available_device_empty_state()

    def _on_available_device_list_model_changed(self, *args) -> None:
        """Qt model signal slot: keep empty-state visibility in sync after any list mutation."""
        self._update_available_device_empty_state_visibility()

    def _on_ui_constraints_disabled(self) -> None:
        """Handle the UI constraints disabled event."""
        self.add_list_items_placeholder(self.ui.available_device_list)
        self._update_available_device_empty_state_visibility()

    def _on_authentification_succeeded(self, device: str) -> None:
        """Handle the authentification succeeded event."""
        for item in self.ui.available_device_list.iter_items():
            item.set_badge("trusted")
        item = DeviceItem.add_to_list(
            self.ui.available_device_list,
            text=device,
            type="available",
            badge="active",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_primary,
            last_communication=self.texts.placeholder_last_communication_active,
            alert_highlight=True,
        )
        self.ui.available_device_list.setCurrentItem(item)
        self.ui.available_device_list.sortItems()
        self._update_available_device_empty_state_visibility()

    def _on_device_selected(self, item: DeviceItem) -> None:
        """Handle the device selected event."""
        if item is None:
            return
        view_signals.DeviceSelectionRequested.emit(item.get_text())

    def _on_device_selection_succeeded(self, device: str) -> None:
        """
        Handle the device selection succeeded event.
        """
        selected_item = self.ui.available_device_list.currentItem()
        if selected_item is None:
            return
        for list_item in self.ui.available_device_list.iter_items():
            list_item.set_badge("trusted")
        selected_item.set_badge("active")

    def _on_devices_updated(self, devices: list[str]) -> None:
        """Handle the devices updated event."""
        self.ui.available_device_list.clear()
        for device in devices:
            DeviceItem.add_to_list(
                self.ui.available_device_list, text=device, type="available"
            )
        self.ui.available_device_list.sortItems()
        self._update_available_device_empty_state_visibility()

    def _on_refresh_button_clicked(self) -> None:
        """Handle the refresh button click event."""
        logger.info("Available device list refresh requested.")
        view_signals.RefreshDeviceListRequested.emit()

    def _on_trash_button_clicked(self) -> None:
        """Handle the trash button click event."""
        logger.info("Remove all devices requested.")
        self.ui.available_device_list.clear()
        self._update_available_device_empty_state_visibility()

    def _sort_available_device_list(self) -> None:
        """Sort the available device list."""
        self.ui.available_device_list.sortItems()

    def current_device(self) -> Optional[DeviceItem]:
        """Get the current device item."""
        return self.ui.available_device_list.currentItem()

    def is_panel_visible(self) -> bool:
        """Check if the device panel is visible."""
        return bool(self.ui.expand_button.property("toggle"))

    def _reduced_height(self) -> int:
        """Height of the panel when reduced (header only): layout padding + header size."""
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        """Show the device panel."""
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_TOPBAR_INSET.value))
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )

    def hide_panel(self) -> None:
        """Hide the device panel."""
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_TOPBAR.value))
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the device panel."""
        if self.ui.expand_button.property("toggle"):
            # Reduce: hide body and constrain height so the panel under can grow.
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_TOPBAR.value))
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        else:
            # Expand: show body and allow panel to grow again.
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_TOPBAR_INSET.value))
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        # Notify parent layout so space is reallocated (panel below gets more height when reduced).
        self.updateGeometry()

    def _on_highlight_pulse_tick(self) -> None:
        """Update device list border intensity from a sine wave (smooth fade in/out)."""
        cycle_ms = Settings.ANIMATION.ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS
        elapsed = self._highlight_elapsed.elapsed()
        level = compute_sine_pulse_level(elapsed, cycle_ms)
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", level
        )

    def start_highlight_attention(self) -> None:
        """Start smooth pulse highlight (soft red border) on paired and available device lists."""
        self.stop_highlight_attention()
        self._highlight_elapsed.start()
        self._highlight_pulse_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_UPDATE_MS
        )
        self._highlight_stop_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_DURATION
        )

    def stop_highlight_attention(self) -> None:
        """Stop the device list highlight animation and restore default border."""
        self._highlight_pulse_timer.stop()
        self._highlight_stop_timer.stop()
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", 0
        )

    def add_list_items_placeholder(self, list_widget: List) -> None:
        """Add sample device rows for UI debugging (fake OS / location / activity)."""
        DeviceItem.add_to_list(
            list_widget,
            text=self.texts.placeholder_primary_device,
            type="available",
            device_kind="mobile",
            badge="trusted",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_primary,
            last_communication=self.texts.placeholder_last_communication_active,
        )
        DeviceItem.add_to_list(
            list_widget,
            text=self.texts.placeholder_secondary_device,
            type="available",
            device_kind="mobile",
            badge="trusted",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_primary,
            last_communication=self.texts.placeholder_last_communication_recent,
        )
        DeviceItem.add_to_list(
            list_widget,
            text=self.texts.placeholder_unknown_device,
            type="available",
            device_kind="mobile",
            badge="new",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_secondary,
            last_communication=self.texts.placeholder_last_communication_old,
            alert_highlight=True,
        )
        self._update_available_device_empty_state_visibility()

    def extend_list_items(self) -> None:
        """Extend the list items to show the last communication time and menu button."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, DeviceItem):
                item.extend_device_item()

    def shorten_list_items(self) -> None:
        """Shorten the list items to hide the last communication time and menu button."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, DeviceItem):
                item.shorten_device_item()
