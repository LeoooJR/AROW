"""
This file contains all graphical elements related to the device panel.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Final, Literal, Optional

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QIcon, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from gui import faker as ui_faker
from gui.animation import (
    animate_widget_visibility,
    apply_highlight_level,
    compute_sine_pulse_level,
)
from gui.colors import Theme
from gui.components import (
    GroupBox,
    HelperText,
    List,
    PanelTitle,
    PlaceHolder,
    ToolButton,
)
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
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
        super().resizeEvent(event)
        self._device_item._sync_size_hint()

    def enterEvent(self, event: QEvent) -> None:
        super().enterEvent(event)
        self._device_item.set_hovered(True)

    def leaveEvent(self, event: QEvent) -> None:
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
        return self._id

    @property
    def name(self) -> str:
        return self._text

    @name.setter
    def name(self, value: str) -> None:
        self._text = value
        self.setToolTip(value)
        self._apply_text_display_mode()
        self._sync_size_hint()

    @property
    def operating_system(self) -> str:
        return self._operating_system

    @operating_system.setter
    def operating_system(self, value: str) -> None:
        self._operating_system = value
        self._refresh_subtitle()
        self._sync_size_hint()

    @property
    def location(self) -> str:
        return self._location

    @location.setter
    def location(self, value: str) -> None:
        self._location = value
        self._refresh_subtitle()
        self._sync_size_hint()

    def _refresh_subtitle(self) -> None:
        """Refresh the subtitle label with the operating system and location."""
        self._apply_text_display_mode()

    def _subtitle_text(self) -> str:
        chunks: list[str] = []
        if self._operating_system:
            chunks.append(self._operating_system)
        if self._location:
            chunks.append(self._location)
        return " · ".join(chunks) if chunks else self.texts.empty_subtitle

    @staticmethod
    def _elided_text(label: QLabel, text: str) -> str:
        width = max(1, label.contentsRect().width())
        return QFontMetrics(label.font()).elidedText(
            text, Qt.TextElideMode.ElideRight, width
        )

    def _set_label_text(self, label: QLabel, text: str) -> None:
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
        return self._alert_highlight

    @alert_highlight.setter
    def alert_highlight(self, value: bool) -> None:
        self._alert_highlight = value
        self.ui.row.setProperty("alert", value)
        self.ui.row.style().unpolish(self.ui.row)
        self.ui.row.style().polish(self.ui.row)
        self.ui.row.update()

    @property
    def badge(self) -> DeviceBadge:
        return self._badge

    @badge.setter
    def badge(self, value: DeviceBadge) -> None:
        self._badge = value
        self._apply_badge()
        self._sync_size_hint()

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
                QIcon(icon_qt_path(GenericIcons.CHECK)).pixmap(
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

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
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
        return self._device_kind

    @device_kind.setter
    def device_kind(self, value: DeviceKind) -> None:
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

    def set_hovered(self, hovered: bool) -> None:
        """Apply hover state to the custom list row widget."""
        self.ui.row.setProperty("hovered", hovered)
        self._refresh_row_style()

    def set_selected(self, selected: bool) -> None:
        """Apply selection state to the custom row widget used by QListWidget."""
        self.ui.row.setProperty("selected", selected)
        self._refresh_row_style()

    def _refresh_row_style(self) -> None:
        self.ui.row.style().unpolish(self.ui.row)
        self.ui.row.style().polish(self.ui.row)
        self.ui.row.update()

    def _list_viewport_width(self) -> int | None:
        lw = self.listWidget()
        if lw is None:
            return None
        width = lw.viewport().width()
        return width if width > 0 else None

    def _can_request_expanded_list_width(self) -> bool:
        lw = self.listWidget()
        if lw is None:
            return False
        window = lw.window()
        return window.width() >= Settings.DIMENSION.WINDOW_MIN_WIDTH

    def _preferred_row_width(self, natural_width: int) -> int:
        return (
            Settings.LIST.DEVICE_ITEM_ROW_EXTENDED_PREFERRED_WIDTH
            if self._is_extended
            else Settings.LIST.DEVICE_ITEM_ROW_COMPACT_PREFERRED_WIDTH
        )

    def _prepare_text_measurement(self) -> None:
        subtitle = self._subtitle_text()
        self.ui.name_label.setWordWrap(False)
        self.ui.subtitle_label.setWordWrap(False)
        self._set_label_text(self.ui.name_label, self._text)
        self._set_label_text(self.ui.subtitle_label, subtitle)

    def _sync_size_hint(self) -> None:
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

    def extend_device_item(self) -> None:
        """Extend the device item to show the last communication time."""
        if self._is_extended:
            return
        self._is_extended = True
        self._set_compact_badge_layout()
        self._apply_text_display_mode()
        self.ui.time_label.show()  # Show the last communication time
        self.ui.trash_button.show()
        self._sync_size_hint()

    def shorten_device_item(self) -> None:
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


class DeviceState(QGroupBox):

    @dataclass(frozen=True)
    class Text:
        """Template strings for the device state summary group."""

        title: Final[str] = "About device"
        state: Final[str] = "State: <state>"
        operating_system: Final[str] = "Operating system: <operating_system>"
        last_communication_prefix: Final[str] = "Last communication: "

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
        self._last_communication_at: dt.datetime | None = None

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

        last_communication = QLabel(
            self.texts.last_communication_prefix
            + format_last_communication_short(None),
            self,
        )
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

    def set_last_communication(
        self,
        value: dt.datetime | None,
        *,
        now: dt.datetime | None = None,
    ) -> None:
        """Set the stored instant and refresh the about-device line."""
        self._last_communication_at = value
        self.ui.last_communication.setText(
            self.texts.last_communication_prefix
            + format_last_communication_short(value, now=now)
        )

    def refresh_last_communication_display(
        self, *, now: dt.datetime | None = None
    ) -> None:
        """Re-apply formatting using the stored instant (for timer ticks)."""
        self.set_last_communication(self._last_communication_at, now=now)

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
            parent=None,
            text=self.texts.title,
            icon_path=icon_qt_path(GenericIcons.DEVICE),
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

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.title.set_leading_icon_path(
            icon_qt_path_for_theme(theme, GenericIcons.DEVICE)
        )

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
        select_helper_text: Final[str] = "Select a device to work with"
        available_devices_group_title: Final[str] = "Available devices"
        placeholder_primary_device: Final[str] = field(
            default_factory=ui_faker.generate_android_device_model
        )
        placeholder_secondary_device: Final[str] = field(
            default_factory=ui_faker.generate_android_device_model
        )
        placeholder_unknown_device: Final[str] = "Unknown Device"
        placeholder_operating_system: Final[str] = field(
            default_factory=ui_faker.generate_android_release_label
        )
        placeholder_location_primary: Final[str] = field(
            default_factory=ui_faker.generate_city_state_location
        )
        placeholder_location_secondary: Final[str] = field(
            default_factory=ui_faker.generate_city_state_location
        )
        placeholder_last_communication_active: Final[str] = "Active now"
        placeholder_last_communication_recent: Final[str] = "30 min ago"
        placeholder_last_communication_old: Final[str] = "2 hours ago"
        placeholder_primary_device_id: Final[str] = field(
            default_factory=lambda: str(uuid.uuid4())
        )
        placeholder_secondary_device_id: Final[str] = field(
            default_factory=lambda: str(uuid.uuid4())
        )
        placeholder_unknown_device_id: Final[str] = field(
            default_factory=lambda: str(uuid.uuid4())
        )

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
            parent=self,
            text=self.texts.title,
            icon_path=icon_qt_path(GenericIcons.DEVICE),
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

        available_device_list = List(None)
        available_device_list.setObjectName("availabe-device-list")
        available_device_empty_state = PlaceHolder(
            available_device_list.viewport(),
            text=self.texts.empty_state,
            minimum_width=0,
            minimum_height=0,
            icon=GenericIcons.DEVICE_PLACEHOLDER,
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
            icon=GenericIcons.PLUS,
            tooltip=self.texts.add_device_tooltip,
        )
        add_device_button.setEnabled(True)
        add_device_button.setObjectName("add-device-button")

        refresh_button = ToolButton(
            self,
            icon=GenericIcons.ARROW_CLOCKWISE,
            tooltip=self.texts.refresh_button_tooltip,
        )
        refresh_button.setEnabled(True)
        refresh_button.setObjectName("refresh-button")

        buttons_wrapper = GridLayoutWrapper(
            self,
            widgets=[
                (add_device_button, 0, 0),
                (refresh_button, 0, 1),
            ],
            spacing=Settings.SPACING.SM,
        )
        buttons_wrapper.setObjectName("available-device-actions")

        available_device_wrapper = HorizontalLayoutWrapper(
            self,
            widgets=[available_device_list, buttons_wrapper],
            spacing=Settings.SPACING.MD,
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
        available_device_group_box.setObjectName("available-device-group-box")

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

        self._last_communication_refresh_timer = QTimer(self)
        self._last_communication_refresh_timer.setSingleShot(False)
        self._last_communication_refresh_timer.timeout.connect(
            self.refresh_last_communication_timestamps
        )
        self._last_communication_refresh_timer.setInterval(
            Settings.LIST.LAST_COMMUNICATION_REFRESH_MS
        )
        self._last_communication_refresh_timer.start()

        self._finalize_ui_hooks()
        self._update_available_device_empty_state_visibility()

    def refresh_last_communication_timestamps(
        self, *, now: dt.datetime | None = None
    ) -> None:
        """Recompute all live last-communication labels (QTimer slot and tests)."""
        ref = now if now is not None else dt.datetime.now()
        for list_item in self.ui.available_device_list.iter_items():
            if isinstance(list_item, DeviceItem):
                list_item.refresh_last_communication_label(now=ref)
        self.ui.device_state.refresh_last_communication_display(now=ref)

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
            self._sync_available_device_item_size_hints()
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

        #### Signals for selecting a device workflow (authentification, selection) ####
        self.ui.add_device_button.clicked.connect(view_signals.AddDeviceRequested.emit)
        view_signals.AuthentificationSucceeded.connect(
            self._on_authentification_succeeded
        )
        self.ui.available_device_list.itemClicked.connect(self._on_device_selected)
        self.ui.available_device_list.itemSelectionChanged.connect(
            self._sync_available_device_selection_state
        )
        view_signals.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        view_signals.DeviceSelectionFailed.connect(self._on_device_selection_failed)
        view_signals.DevicesUpdated.connect(self._on_devices_updated)
        self.ui.refresh_button.clicked.connect(self._on_refresh_button_clicked)
        view_signals.RemoveDeviceRequested.connect(self._on_remove_device_requested)

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
        placeholder.ui.svg.setFixedSize(icon_size, icon_size)
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
        self._sync_available_device_selection_state()
        self._sync_available_device_item_size_hints()

    def _sync_available_device_selection_state(self) -> None:
        """Mirror QListWidget selection onto custom row widgets."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, DeviceItem):
                item.set_selected(item.isSelected())

    def _sync_available_device_item_size_hints(self) -> None:
        """Re-measure custom rows when the list viewport width changes."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, DeviceItem):
                item._sync_size_hint()

    def _on_ui_constraints_disabled(self) -> None:
        """Handle the UI constraints disabled event."""
        self.add_list_items_placeholder(self.ui.available_device_list)
        self._on_available_device_list_model_changed()

    def _on_authentification_succeeded(self, device: dict) -> None:
        """Handle the authentification succeeded event."""
        for item in self.ui.available_device_list.iter_items():
            item.badge = "trusted"
        item = DeviceItem.add_to_list(
            self.ui.available_device_list,
            id=device["id"],
            text=device["name"],
            type="available",
            badge="active",
            operating_system=device["os"],
            location="N/A",
            last_communication=device["last_communication"],
            alert_highlight=True,
        )
        self.ui.available_device_list.setCurrentItem(item)
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_device_selected(self, item: DeviceItem) -> None:
        """Handle the device selected event."""
        if item is None:
            return
        view_signals.DeviceSelectionRequested.emit(item.id, item.name)

    def _on_device_selection_succeeded(self, device: dict) -> None:
        """
        Handle the device selection succeeded event.
        """
        selected_item = self.ui.available_device_list.currentItem()
        if selected_item is None:
            return
        for list_item in self.ui.available_device_list.iter_items():
            list_item.badge = "trusted"
        selected_item.badge = "active"
        self._on_available_device_list_model_changed()

    def _on_device_selection_failed(self, device: dict) -> None:
        """Handle the device selection failed event."""
        self.ui.available_device_list.setCurrentItem(None)
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_devices_updated(self, devices: list[dict]) -> None:
        """Handle the devices updated event."""
        self.ui.available_device_list.clear()
        for device in devices:
            DeviceItem.add_to_list(
                self.ui.available_device_list,
                id=device["id"],
                text=device["name"],
                type="available",
                device_kind="mobile",
                badge="new",
                operating_system=device["os"],
                location="N/A",
                last_communication=device["last_communication"],
            )
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_refresh_button_clicked(self) -> None:
        """Handle the refresh button click event."""
        logger.info("Available device list refresh requested.")
        view_signals.RefreshDeviceListRequested.emit()

    def _on_remove_device_requested(self, id: str) -> None:
        """Handle the remove device requested event."""
        logger.info("Remove device requested.", id=id)
        for item_index, item in enumerate(
            self.ui.available_device_list.iter_items(), start=0
        ):
            if item.id == id:
                removed_item = self.ui.available_device_list.takeItem(item_index)
                if removed_item is not None:
                    del removed_item
                    break
        self._on_available_device_list_model_changed()

    def is_panel_visible(self) -> bool:
        """Check if the device panel is visible."""
        return bool(self.ui.expand_button.property("toggle"))

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh toolbar, header, empty state, and row icons for ``theme``."""
        self.ui.title.set_leading_icon_path(
            icon_qt_path_for_theme(theme, GenericIcons.DEVICE)
        )
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_TOPBAR_INSET if inset else GenericIcons.LAYOUT_TOPBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.available_device_empty_state.apply_theme_icons(theme)
        self.ui.add_device_button.apply_theme_icons(theme)
        self.ui.refresh_button.apply_theme_icons(theme)
        for lw_item in self.ui.available_device_list.iter_items():
            if isinstance(lw_item, DeviceItem):
                lw_item.apply_theme_icons(theme)

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
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR_INSET)
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
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR)
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
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_TOPBAR)
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
            id=self.texts.placeholder_primary_device_id,
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
            id=self.texts.placeholder_secondary_device_id,
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
            id=self.texts.placeholder_unknown_device_id,
            text=self.texts.placeholder_unknown_device,
            type="available",
            device_kind="mobile",
            badge="new",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_secondary,
            last_communication=self.texts.placeholder_last_communication_old,
            alert_highlight=True,
        )
        self._on_available_device_list_model_changed()

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
