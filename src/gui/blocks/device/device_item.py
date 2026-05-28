"""Device-list row items and formatting helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Final, Literal

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QIcon, QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from gui.colors import Theme
from gui.components import StatusBadge, ToolButton
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper

DeviceKind = Literal["mobile"]
DeviceBadge = Literal["none", "active", "trusted", "new"]

# Relative labels switch to absolute date/time after this many days.
_LAST_COMMUNICATION_RELATIVE_MAX_DAYS = 7


def format_last_communication_short(
    value: dt.datetime | None,
    *,
    now: dt.datetime | None = None,
) -> str:
    """User-facing label for last contact time (relative for recent, absolute when older).

    Naive datetimes are treated as local wall time, consistent with ``Phone`` construction.

    Args:
        value: Last communication instant, or ``None`` if unknown.
        now: Reference "current" time for tests; default ``datetime.now()`` (naive local).
    """
    if value is None:
        return "Never"
    current = now if now is not None else dt.datetime.now()
    if value > current:
        return "Just now"
    delta = current - value
    secs = int(delta.total_seconds())
    if secs < 60:
        return "Just now"
    minutes = secs // 60
    if minutes < 60:
        if minutes == 1:
            return "1 minute ago"
        return f"{minutes} minutes ago"
    hours = secs // 3600
    if hours < 24:
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    days = secs // 86400
    if days < _LAST_COMMUNICATION_RELATIVE_MAX_DAYS:
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"
    # Compact English timestamp (locale-neutral).
    h12 = value.strftime("%I").lstrip("0") or "12"
    mm = value.strftime("%M")
    ampm = value.strftime("%p")
    return f"{value.strftime('%b')} {value.day}, {value.year}, {h12}:{mm} {ampm}"


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
        """Refresh the owning item size hint after row resize."""
        super().resizeEvent(event)
        self._device_item._sync_size_hint()

    def enterEvent(self, event: QEvent) -> None:
        """Mark the owning item hovered when the mouse enters the row."""
        super().enterEvent(event)
        self._device_item.set_hovered(True)

    def leaveEvent(self, event: QEvent) -> None:
        """Clear hover state when the mouse leaves the row."""
        super().leaveEvent(event)
        self._device_item.set_hovered(False)


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
        trash_button: Final[str] = ""
        trash_button_tooltip: Final[str] = "Remove device"
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
        trash_button: ToolButton
        icon_label: QLabel
        helper_text: str

    def __init__(
        self,
        parent=None,
        id: str | None = None,
        text: str | None = None,
        type: str = "available",
        *,
        device_kind: DeviceKind = "mobile",
        badge: DeviceBadge = "none",
        operating_system: str = "",
        location: str = "",
        last_communication: str | dt.datetime | None = "",
        alert_highlight: bool = False,
    ):
        """Create a styled device entry for embedding in a ``QListWidget``.

        Args:
            parent: Optional list widget or owner passed to ``QListWidgetItem``.
            id: Device unique identifier.
            text: Primary device name; falls back to default when omitted.
            type: Device category label used in helper/status copy.
            device_kind: Fixed literal for supported device kinds (currently mobile).
            badge: Visual trust/activity badge variant.
            operating_system: OS line shown in the subtitle stack.
            location: Location line shown in the subtitle stack.
            last_communication: Right-side recency when extended: plain string (fixed
                label), datetime (live relative/absolute formatting), or None (Never).
            alert_highlight: When True, apply attention styling to the row.
        """
        super().__init__(parent)

        self.ui: DeviceItem.UI
        self.texts: DeviceItem.Text = DeviceItem.Text()

        display_name = text if text is not None else self.texts.default_name
        helper_text = f"{type.capitalize()} device"
        whats_this_text = (
            f"A {type.capitalize()} device which can be used to work with."
        )

        self.setToolTip(display_name)
        self.setStatusTip(helper_text)
        self.setWhatsThis(whats_this_text)

        self.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.setIcon(QIcon())  # Icon is not set using the default list widget method

        # Device item properties
        self._id: str | None = id
        self._text: str = display_name
        self._device_kind: DeviceKind = device_kind
        self._badge: DeviceBadge = badge
        self._operating_system: str = operating_system
        self._location: str = location
        self._last_communication_is_static: bool = isinstance(last_communication, str)
        self._last_communication_live_at: dt.datetime | None = (
            None if self._last_communication_is_static else last_communication
        )

        # Device item UI properties
        self._is_extended: bool = False
        self._uses_compact_badge_layout: bool = False
        self._sync_size_hint_in_progress: bool = False

        row = _DeviceItemRowWidget(self)
        row.setObjectName("device-item-row")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ### Icon label ###

        icon_path = icon_qt_path(GenericIcons.DEVICE)
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

        ### Device name label ###

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

        ### Badge container ###

        badge_container = HorizontalLayoutWrapper(
            row,
            widgets=[],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        badge_container.setObjectName("device-item-badge-container")
        badge_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ### Subtitle label ###

        subtitle_label = QLabel(row)
        subtitle_label.setObjectName("device-item-subtitle")
        subtitle_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        DeviceItem._configure_wrapped_line_label(
            subtitle_label, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        ### Subtitle host ###

        subtitle_host = VerticalLayoutWrapper(
            row,
            widgets=[subtitle_label],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        subtitle_host.setObjectName("device-item-subtitle-host")
        subtitle_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ### Last communication time label ###

        time_label = QLabel(row)
        time_label.setObjectName("device-item-time")
        time_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        DeviceItem._configure_wrapped_line_label(
            time_label, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        # Set the last communication time label text based on the last communication property (dynamic or static)
        if self._last_communication_is_static:
            time_label.setText(last_communication)
        else:
            time_label.setText(
                format_last_communication_short(self._last_communication_live_at)
            )
        time_label.hide()  # Hide the last communication time by default (shown in extended mode)

        ### Trash button ###

        trash_button = ToolButton(
            row,
            icon=GenericIcons.TRASH,
            tooltip=self.texts.trash_button_tooltip,
        )
        trash_button.setObjectName("device-item-trash")
        trash_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        trash_button.hide()

        ### Title row ###

        title_row = HorizontalLayoutWrapper(
            row,
            widgets=[name_label, badge_container],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_NAME_BADGE_GAP,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_end=True,
        )
        title_row.setObjectName("device-item-title-row")
        title_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ### Center layout ###

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

        ### Right wrap layout ###

        right_wrap = HorizontalLayoutWrapper(
            row,
            widgets=[time_label, trash_button],
            spacing=Settings.LIST.DEVICE_ITEM_ROW_RIGHT_GAP,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        right_wrap.setObjectName("device-item-right-wrap")
        right_wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        ### Main row layout ###

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
            trash_button=trash_button,
            icon_label=icon_label,
            helper_text=helper_text,
        )

        self._apply_badge()
        self._set_compact_badge_layout()
        self._refresh_subtitle()
        self.alert_highlight = alert_highlight

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
        self.ui.trash_button.setSizePolicy(
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
            self.ui.trash_button, Qt.AlignmentFlag.AlignVCenter
        )
        self.ui.right_wrap.get_layout().setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def _connect_signals(self) -> None:
        """Signals for the device row (menu, future actions)."""
        self.ui.trash_button.clicked.connect(self._on_trash_button_clicked)

    @property
    def id(self) -> str | None:
        """Return the device identifier carried by this row."""
        return self._id

    @property
    def name(self) -> str:
        """Return the display name shown by this row."""
        return self._text

    @name.setter
    def name(self, value: str) -> None:
        """Update the display name and refresh row measurement."""
        self._text = value
        self.setToolTip(value)
        self._apply_text_display_mode()
        self._sync_size_hint()

    @property
    def operating_system(self) -> str:
        """Return the operating-system subtitle value."""
        return self._operating_system

    @operating_system.setter
    def operating_system(self, value: str) -> None:
        """Update the operating-system subtitle value."""
        self._operating_system = value
        self._refresh_subtitle()
        self._sync_size_hint()

    @property
    def location(self) -> str:
        """Return the location subtitle value."""
        return self._location

    @location.setter
    def location(self, value: str) -> None:
        """Update the location subtitle value."""
        self._location = value
        self._refresh_subtitle()
        self._sync_size_hint()

    def _refresh_subtitle(self) -> None:
        """Refresh the subtitle label with the operating system and location."""
        self._apply_text_display_mode()

    def _subtitle_text(self) -> str:
        """Compose the subtitle from operating system and location values."""
        chunks: list[str] = []
        if self._operating_system:
            chunks.append(self._operating_system)
        if self._location:
            chunks.append(self._location)
        return " · ".join(chunks) if chunks else self.texts.empty_subtitle

    @staticmethod
    def _elided_text(label: QLabel, text: str) -> str:
        """Return text elided to fit the current label width."""
        width = max(1, label.contentsRect().width())
        return QFontMetrics(label.font()).elidedText(
            text, Qt.TextElideMode.ElideRight, width
        )

    def _set_label_text(self, label: QLabel, text: str) -> None:
        """Set label text only when it has changed."""
        if label.text() != text:
            label.setText(text)

    def _apply_text_display_mode(self) -> None:
        """List rows use single-line elision so cards keep a stable height."""
        subtitle = self._subtitle_text()
        self.ui.name_label.setWordWrap(False)
        self.ui.subtitle_label.setWordWrap(False)
        self._set_label_text(
            self.ui.name_label, self._elided_text(self.ui.name_label, self._text)
        )
        self._set_label_text(
            self.ui.subtitle_label,
            self._elided_text(self.ui.subtitle_label, subtitle),
        )

    @property
    def last_communication(self) -> str | dt.datetime | None:
        """Return the stored live last-communication instant, if any."""
        return self._last_communication_live_at

    @last_communication.setter
    def last_communication(
        self,
        value: str | dt.datetime | None,
        *,
        now: dt.datetime | None = None,
    ) -> None:
        """Set the right-side time label: static string or live datetime/None."""
        if isinstance(value, str):
            self._last_communication_is_static = True
            self._last_communication_live_at = None
            self.ui.time_label.setText(value)
        else:
            self._last_communication_is_static = False
            self._last_communication_live_at = value
            self.ui.time_label.setText(format_last_communication_short(value, now=now))
        self._sync_size_hint()

    def refresh_last_communication_label(
        self, *, now: dt.datetime | None = None
    ) -> None:
        """Recompute label from stored live instant (no-op for static/placeholder rows)."""
        if self._last_communication_is_static:
            return
        self.ui.time_label.setText(
            format_last_communication_short(self._last_communication_live_at, now=now)
        )
        self._sync_size_hint()

    @property
    def alert_highlight(self) -> bool:
        """Return whether the row is rendered with alert styling."""
        return self._alert_highlight

    @alert_highlight.setter
    def alert_highlight(self, value: bool) -> None:
        """Toggle alert styling on the custom row widget."""
        self._alert_highlight = value
        self.ui.row.setProperty("alert", value)
        self.ui.row.style().unpolish(self.ui.row)
        self.ui.row.style().polish(self.ui.row)
        self.ui.row.update()

    @property
    def badge(self) -> DeviceBadge:
        """Return the current badge variant."""
        return self._badge

    @badge.setter
    def badge(self, value: DeviceBadge) -> None:
        """Update the badge variant and refresh row measurement."""
        self._badge = value
        self._apply_badge()
        self._sync_size_hint()

    def _apply_badge(self) -> None:
        """Rebuild the badge label area from the current badge variant."""
        layout = self.ui.badge_container.layout()
        assert layout is not None
        self._clear_layout(layout)
        if self._badge == "none":
            return
        if self._badge == "active":
            lab = StatusBadge(
                text=self.texts.active_badge,
                kind="active",
                object_name="device-item-badge",
                property_name="device-item-badge",
                size_policy=(
                    QSizePolicy.Policy.Maximum,
                    QSizePolicy.Policy.Preferred,
                ),
            )
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
                QIcon(icon_qt_path(GenericIcons.CHECK)).pixmap(
                    QSize(self._SUBTITLE_ICON_PX, self._SUBTITLE_ICON_PX)
                )
            )
            tx = StatusBadge(
                text=self.texts.trusted_badge,
                kind="trusted-text",
                object_name="device-item-badge",
                property_name="device-item-badge",
                size_policy=(
                    QSizePolicy.Policy.Maximum,
                    QSizePolicy.Policy.Preferred,
                ),
            )
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
            lab = StatusBadge(
                text=self.texts.new_badge,
                kind="new",
                object_name="device-item-badge",
                property_name="device-item-badge",
                size_policy=(
                    QSizePolicy.Policy.Maximum,
                    QSizePolicy.Policy.Preferred,
                ),
            )
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

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        """Remove and delete every widget item from ``layout``."""
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _set_compact_badge_layout(self) -> None:
        """Move the badge below the name so narrow rows do not clip labels."""
        if self._uses_compact_badge_layout:
            return
        title_layout = self.ui.title_row.get_layout()
        center_layout = self.ui.center.get_layout()
        title_layout.removeWidget(self.ui.badge_container)
        center_layout.insertWidget(1, self.ui.badge_container)
        self._uses_compact_badge_layout = True

    def _set_extended_badge_layout(self) -> None:
        """Restore the wider inline name/badge layout used by expanded rows."""
        if not self._uses_compact_badge_layout:
            return
        center_layout = self.ui.center.get_layout()
        title_layout = self.ui.title_row.get_layout()
        center_layout.removeWidget(self.ui.badge_container)
        title_layout.insertWidget(1, self.ui.badge_container)
        self._uses_compact_badge_layout = False

    @property
    def device_kind(self) -> DeviceKind:
        """Return the logical device kind represented by this row."""
        return self._device_kind

    @device_kind.setter
    def device_kind(self, value: DeviceKind) -> None:
        """Update the logical device kind and leading icon."""
        self._device_kind = value
        path = icon_qt_path(GenericIcons.DEVICE)
        self.ui.icon_label.setPixmap(
            QIcon(path).pixmap(QSize(self._ICON_INNER_PX, self._ICON_INNER_PX))
        )

    @classmethod
    def add_to_list(
        cls,
        list_widget: QListWidget,
        *,
        id: str | None = None,
        text: str | None = None,
        type: str = "available",
        device_kind: DeviceKind = "mobile",
        badge: DeviceBadge = "none",
        operating_system: str = "",
        location: str = "",
        last_communication: str | dt.datetime | None = "",
        alert_highlight: bool = False,
    ) -> "DeviceItem":
        """Add a device item to the list widget and sync the size hint."""
        item = cls(
            None,
            id=id,
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

    @property
    def row_widget(self) -> QWidget:
        """Return the custom row widget embedded in the device list."""
        return self.ui.row

    @property
    def trash_button(self) -> ToolButton:
        """Return the row remove-device button."""
        return self.ui.trash_button

    def set_hovered(self, hovered: bool) -> None:
        """Apply hover state to the custom list row widget."""
        self.ui.row.setProperty("hovered", hovered)
        self._refresh_row_style()

    def set_selected(self, selected: bool) -> None:
        """Apply selection state to the custom row widget used by QListWidget."""
        self.ui.row.setProperty("selected", selected)
        self._refresh_row_style()

    def _refresh_row_style(self) -> None:
        """Re-polish the row after dynamic style properties change."""
        self.ui.row.style().unpolish(self.ui.row)
        self.ui.row.style().polish(self.ui.row)
        self.ui.row.update()

    def _list_viewport_width(self) -> int | None:
        """Return the current list viewport width used for row measurement."""
        lw = self.listWidget()
        if lw is None:
            return None
        width = lw.viewport().width()
        return width if width > 0 else None

    def _can_request_expanded_list_width(self) -> bool:
        """Return whether the window is wide enough for expanded row width hints."""
        lw = self.listWidget()
        if lw is None:
            return False
        window = lw.window()
        return window.width() >= Settings.DIMENSION.WINDOW_MIN_WIDTH

    def _preferred_row_width(self, natural_width: int) -> int:
        """Return the preferred width for compact or expanded row presentation."""
        return (
            Settings.LIST.DEVICE_ITEM_ROW_EXTENDED_PREFERRED_WIDTH
            if self._is_extended
            else Settings.LIST.DEVICE_ITEM_ROW_COMPACT_PREFERRED_WIDTH
        )

    def _prepare_text_measurement(self) -> None:
        """Prepare labels with unelided text before measuring natural row size."""
        subtitle = self._subtitle_text()
        self.ui.name_label.setWordWrap(False)
        self.ui.subtitle_label.setWordWrap(False)
        self._set_label_text(self.ui.name_label, self._text)
        self._set_label_text(self.ui.subtitle_label, subtitle)

    def _sync_size_hint(self) -> None:
        """Recalculate the item size hint for the current list width and state."""
        if self._sync_size_hint_in_progress:
            return
        try:
            self._sync_size_hint_in_progress = True
            row = self.ui.row
            if not isValid(row):
                return
            lay = row.layout()
            self._prepare_text_measurement()
            if lay is not None:
                lay.invalidate()
                lay.activate()
            row.updateGeometry()

            viewport_width = self._list_viewport_width()
            natural_width = max(1, row.minimumSizeHint().width())
            preferred_width = self._preferred_row_width(natural_width)
            if self._is_extended and self._can_request_expanded_list_width():
                preferred_width = max(
                    preferred_width,
                    Settings.LIST.DEVICE_ITEM_ROW_EXTENDED_PREFERRED_WIDTH,
                )
            if (
                viewport_width is not None
                and not self._can_request_expanded_list_width()
            ):
                target_width = min(viewport_width, preferred_width)
            else:
                target_width = preferred_width

            if self._is_extended:
                saved = QSize(row.width(), row.height())
                if target_width > 0:
                    row.resize(target_width, saved.height())
                    if lay is not None:
                        lay.activate()
                    row.updateGeometry()
                    self._apply_text_display_mode()
                    if lay is not None:
                        lay.activate()
                    row.updateGeometry()
                sh = row.sizeHint()
                row.resize(saved)
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                h = max(Settings.LIST.DEVICE_ITEM_ROW_MIN_HEIGHT, sh.height())
                w = target_width if target_width > 0 else sh.width()
                self.setSizeHint(QSize(w, h))
            else:
                # Shortened: do not carry over the row's stretched width from the extended
                # state — width must match hidden right column so AdjustToContents can shrink.
                measure_width = target_width
                saved = QSize(row.width(), row.height())
                row.resize(measure_width, saved.height())
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                self._apply_text_display_mode()
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                sh = row.sizeHint()
                row.resize(saved)
                if lay is not None:
                    lay.activate()
                row.updateGeometry()
                h = max(Settings.LIST.DEVICE_ITEM_ROW_MIN_HEIGHT, sh.height())
                self.setSizeHint(QSize(measure_width, h))
        finally:
            self._sync_size_hint_in_progress = False
        lw = self.listWidget()
        if lw is not None:
            lw.viewport().update()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh row icons after a global light/dark switch."""
        p = icon_qt_path_for_theme(theme, GenericIcons.DEVICE)
        self.ui.icon_label.setPixmap(
            QIcon(p).pixmap(QSize(self._ICON_INNER_PX, self._ICON_INNER_PX))
        )
        self.ui.trash_button.apply_theme_icons(theme)
        self._apply_badge()

    ### Extend / shorten core logic ###

    def extend(self) -> None:
        """Extend the device item to show the last communication time."""
        if self._is_extended:
            return
        self._is_extended = True
        self._set_compact_badge_layout()
        self._apply_text_display_mode()
        self.ui.time_label.show()  # Show the last communication time
        self.ui.trash_button.show()
        self._sync_size_hint()

    def shorten(self) -> None:
        """Shorten the device item to hide the last communication time"""
        if not self._is_extended:
            self._set_compact_badge_layout()  # In shortened mode, the badge is below the device name
            self.ui.time_label.hide()
            self.ui.trash_button.hide()
            self._apply_text_display_mode()
            self._sync_size_hint()
            return
        self._is_extended = False
        self._set_compact_badge_layout()  # In shortened mode, the badge is below the device name
        self._apply_text_display_mode()
        self.ui.time_label.hide()  # Hide the last communication time
        self.ui.trash_button.hide()
        self._sync_size_hint()

    ### Slots ###

    def _on_trash_button_clicked(self) -> None:
        """Handle the trash button click event."""
        view_signals.RemoveDeviceRequested.emit(self._id)
