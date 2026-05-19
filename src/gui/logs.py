"""
This file contains all graphical elements related to the logs panel.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from gui import faker as ui_faker
from gui.animation import animate_widget_visibility
from gui.colors import Theme
from gui.elements import (
    File,
    GroupBox,
    HelperText,
    List,
    PanelTitle,
    ToolButton,
)
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper

ActivityCategory = Literal["simulation", "device", "location", "adb", "file", "system"]
ActivityLevel = Literal["info", "success", "warning", "error", "start", "stop"]


@dataclass(frozen=True, slots=True)
class ActivityLogEntry:
    """Session-local, user-facing activity item displayed in the log panel."""

    id: str
    timestamp: dt.datetime
    category: ActivityCategory
    level: ActivityLevel
    message: str
    detail: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


def _coerce_activity_timestamp(timestamp: dt.datetime | None) -> dt.datetime:
    """Return a display timestamp without timezone branching in row rendering."""
    return timestamp if timestamp is not None else dt.datetime.now()


def _format_activity_date(timestamp: dt.datetime) -> str:
    today = dt.datetime.now().date()
    if timestamp.date() == today:
        return f"Today, {timestamp:%d %b}"
    return timestamp.strftime("%A, %d %b").title()


class ActivityDateHeaderItem(QListWidgetItem):
    """Date separator inserted into the activity list."""

    @classmethod
    def add_to_list(
        cls, list_widget: QListWidget, label: str
    ) -> "ActivityDateHeaderItem":
        item = cls()
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        row = QLabel(label)
        row.setObjectName("activity-log-date-header")
        row.setProperty("activity-log-date-header", True)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.setContentsMargins(
            Settings.SPACING.XS,
            Settings.SPACING.SM,
            Settings.SPACING.XS,
            Settings.SPACING.XS,
        )
        list_widget.addItem(item)
        list_widget.setItemWidget(item, row)
        item.setSizeHint(row.sizeHint())
        return item


class ActivityFilterSectionLabel(QLabel):
    """Small section label used in the activity filter popup."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("activity-log-filter-section")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )


class ActivityFilterSeparator(QFrame):
    """Subtle divider used between filter groups."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("activity-log-filter-separator")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class ActivityFilterOption(QCheckBox):
    """Styled checkable row used by the activity filter popup."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._label = text
        self.setObjectName("activity-log-filter-option")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )
        self.toggled.connect(self.sync_display)
        self.sync_display()

    def sync_display(self) -> None:
        marker = "✓" if self.isChecked() else " "
        self.setText(f"{marker} {self._label}")


class _ActivityLogItemRowWidget(QWidget):
    """Keep custom activity rows responsive to hover and width changes."""

    def __init__(self, activity_item: "ActivityLogItem"):
        super().__init__()
        self._activity_item = activity_item

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._activity_item._sync_size_hint()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self._activity_item.set_hovered(True)

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._activity_item.set_hovered(False)


class ActivityLogItem(QListWidgetItem):
    """Rich activity-log row with category icon, status, time, and optional detail."""

    _CATEGORY_ICON: Final[dict[ActivityCategory, GenericIcons]] = {
        "simulation": GenericIcons.PLAY,
        "device": GenericIcons.DEVICE,
        "location": GenericIcons.LOCATION,
        "adb": GenericIcons.LAPTOP,
        "file": GenericIcons.FILE,
        "system": GenericIcons.INFO,
    }
    _LEVEL_LABEL: Final[dict[ActivityLevel, str]] = {
        "info": "Info",
        "success": "OK",
        "warning": "Warn",
        "error": "Error",
        "start": "Start",
        "stop": "Stop",
    }

    @dataclass
    class UI:
        row: QWidget
        icon_frame: HorizontalLayoutWrapper
        icon_label: QLabel
        center: VerticalLayoutWrapper
        title_row: HorizontalLayoutWrapper
        message_label: QLabel
        level_label: QLabel
        meta_label: QLabel
        detail_label: QLabel
        time_label: QLabel

    def __init__(self, entry: ActivityLogEntry):
        super().__init__()
        self.entry = entry
        self.ui: ActivityLogItem.UI
        self._sync_size_hint_in_progress = False

        self.setToolTip(entry.message)
        self.setStatusTip(f"{entry.category} · {entry.level}")
        self.setTextAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.setIcon(QIcon())

        row = _ActivityLogItemRowWidget(self)
        row.setObjectName("activity-log-item-row")
        row.setProperty("activity-level", entry.level)
        row.setProperty("activity-category", entry.category)
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        icon_label = QLabel(row)
        icon_label.setObjectName("activity-log-icon")
        icon_label.setPixmap(
            QIcon(icon_qt_path(self._CATEGORY_ICON[entry.category])).pixmap(
                QSize(
                    Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
                    Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
                )
            )
        )
        icon_label.setFixedSize(
            Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
            Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_frame = HorizontalLayoutWrapper(
            row,
            widgets=[icon_label],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        icon_frame.setObjectName("activity-log-icon-frame")
        icon_frame.setProperty("activity-level", entry.level)
        icon_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_frame.setFixedSize(
            Settings.LIST.ACTIVITY_ITEM_ROW_ICON_FRAME,
            Settings.LIST.ACTIVITY_ITEM_ROW_ICON_FRAME,
        )

        message_label = QLabel(entry.message, row)
        message_label.setObjectName("activity-log-message")
        message_label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )
        message_label.setWordWrap(True)
        message_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        message_label.setMinimumWidth(0)

        level_label = QLabel(self._LEVEL_LABEL[entry.level], row)
        level_label.setObjectName("activity-log-level")
        level_label.setProperty("activity-level", entry.level)
        level_label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )
        level_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        level_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        title_row = HorizontalLayoutWrapper(
            row,
            widgets=[message_label, level_label],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        title_row.get_layout().setStretchFactor(message_label, 1)

        meta_label = QLabel(self._meta_text(entry), row)
        meta_label.setObjectName("activity-log-meta")
        meta_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        meta_label.setWordWrap(True)
        meta_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        meta_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        meta_label.setMinimumWidth(0)

        detail_label = QLabel(entry.detail or "", row)
        detail_label.setObjectName("activity-log-detail")
        detail_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        detail_label.setWordWrap(True)
        detail_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        detail_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        detail_label.setMinimumWidth(0)
        detail_label.setVisible(bool(entry.detail))
        detail_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        center = VerticalLayoutWrapper(
            row,
            widgets=[title_row, meta_label, detail_label],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        center.setObjectName("activity-log-center")

        time_label = QLabel(entry.timestamp.strftime("%H:%M:%S"), row)
        time_label.setObjectName("activity-log-time")
        time_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        time_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        main_row = HorizontalLayoutWrapper(
            row,
            widgets=[icon_frame, center, time_label],
            spacing=Settings.LIST.ACTIVITY_ITEM_ROW_ICON_GAP,
            margins=(
                Settings.LIST.ACTIVITY_ITEM_ROW_PADDING_H,
                Settings.LIST.ACTIVITY_ITEM_ROW_PADDING_V,
                Settings.LIST.ACTIVITY_ITEM_ROW_PADDING_H,
                Settings.LIST.ACTIVITY_ITEM_ROW_PADDING_V,
            ),
        )
        main_row.get_layout().setStretchFactor(center, 1)
        main_row.get_layout().setAlignment(icon_frame, Qt.AlignmentFlag.AlignTop)

        row_layout = QVBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(main_row)
        row.setLayout(row_layout)

        self.ui = ActivityLogItem.UI(
            row=row,
            icon_frame=icon_frame,
            icon_label=icon_label,
            center=center,
            title_row=title_row,
            message_label=message_label,
            level_label=level_label,
            meta_label=meta_label,
            detail_label=detail_label,
            time_label=time_label,
        )
        self._sync_size_hint()

    @classmethod
    def add_to_list(
        cls, list_widget: QListWidget, entry: ActivityLogEntry
    ) -> "ActivityLogItem":
        """Add an activity row to ``list_widget`` and keep its custom widget synced."""
        item = cls(entry)
        list_widget.addItem(item)
        list_widget.setItemWidget(item, item.ui.row)
        item._sync_size_hint()
        return item

    @staticmethod
    def _meta_text(entry: ActivityLogEntry) -> str:
        chunks = [entry.category.upper()]
        chunks.extend(f"{key}: {value}" for key, value in entry.metadata.items())
        return " · ".join(chunks)

    def set_selected(self, selected: bool) -> None:
        self.ui.row.setProperty("selected", selected)
        self._refresh_row_style()

    def set_hovered(self, hovered: bool) -> None:
        self.ui.row.setProperty("hovered", hovered)
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
            viewport_width = self._list_viewport_width()
            measure_width = (
                max(1, viewport_width - 2)
                if viewport_width is not None
                else Settings.LIST.ACTIVITY_ITEM_PREFERRED_WIDTH
            )
            hint_width = min(measure_width, Settings.LIST.ACTIVITY_ITEM_PREFERRED_WIDTH)
            saved = QSize(row.width(), row.height())
            row.resize(measure_width, saved.height())
            if lay is not None:
                lay.activate()
            row.updateGeometry()
            sh = row.sizeHint()
            row.resize(saved)
            if lay is not None:
                lay.activate()
            row.updateGeometry()
            self.setSizeHint(
                QSize(
                    hint_width,
                    max(Settings.LIST.ACTIVITY_ITEM_ROW_MIN_HEIGHT, sh.height()),
                )
            )
        finally:
            self._sync_size_hint_in_progress = False


class LogPanel(QFrame):
    """Side panel listing activity logs and the log file summary."""

    @dataclass(frozen=True)
    class Text:
        """Titles, placeholders, and helper copy for the log panel."""

        title: Final[str] = "Activity log"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"
        helper_text: Final[str] = "Logs are saved in the following file"
        file_name: str = field(default_factory=ui_faker.generate_activity_log_filename)
        file_type: str = field(default_factory=ui_faker.generate_activity_log_file_type)
        group_title: Final[str] = "Logs"
        filter_button_tooltip: Final[str] = "Filter activity events"
        events_empty_count: Final[str] = "No events"

    @dataclass
    class UI:
        """Widgets for the log list, file row, and grouped layout."""

        title: PanelTitle
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        activity_header: QWidget
        date_label: QLabel
        event_count_label: QLabel
        filter_button: ToolButton
        filter_menu: QMenu
        logs_list: List
        logs_list_helper_text: HelperText
        file_display_widget: File
        logs_wrapper: VerticalLayoutWrapper
        logs_group_box: GroupBox

    def __init__(self, parent=None):
        """Build the log panel layout and wire expand behavior.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: LogPanel.UI
        self.texts = LogPanel.Text()

        self.setObjectName("log-panel")
        self.setProperty("panel", True)
        self._active_simulation_id: str | None = None
        self._activities: list[ActivityLogEntry] = []
        self._category_filter: set[ActivityCategory] | None = None
        self._level_filter: set[ActivityLevel] | None = None
        self._category_filter_actions: dict[ActivityCategory, QAction] = {}
        self._level_filter_actions: dict[ActivityLevel, QAction] = {}
        self._category_filter_widgets: dict[ActivityCategory, QCheckBox] = {}
        self._level_filter_widgets: dict[ActivityLevel, QCheckBox] = {}

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
            icon_path=icon_qt_path(GenericIcons.LOGS),
        )

        expand_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_BOTTOMBAR_INSET,
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

        logs_list = List(None)
        logs_list.setObjectName("logs-list")
        logs_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        date_label = QLabel("", self)
        date_label.setObjectName("activity-log-current-date")
        date_label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )

        event_count_label = QLabel(self.texts.events_empty_count, self)
        event_count_label.setObjectName("activity-log-event-count")
        event_count_label.setProperty("activity-log-event-count", True)
        event_count_label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_HELPER,
                QFont.Weight.DemiBold,
            )
        )
        event_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        filter_button = ToolButton(
            self,
            icon=GenericIcons.FUNNEL,
            tooltip=self.texts.filter_button_tooltip,
        )
        filter_button.setObjectName("activity-log-filter-button")
        filter_menu = self._build_filter_menu(filter_button)
        filter_button.setMenu(filter_menu)
        filter_button.setPopupMode(ToolButton.ToolButtonPopupMode.InstantPopup)

        activity_header = QWidget(self)
        activity_header.setObjectName("activity-log-header")
        activity_header_layout = QHBoxLayout(activity_header)
        activity_header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        activity_header_layout.setSpacing(Settings.SPACING.XS)
        activity_header_layout.addWidget(date_label, 1)
        activity_header_layout.addWidget(event_count_label, 0)
        activity_header_layout.addWidget(filter_button, 0)

        logs_list_helper_text = HelperText(self, self.texts.helper_text)

        file_display_widget = File(
            None,
            file_name=self.texts.file_name,
            file_type=self.texts.file_type,
            file_save=True,
        )

        logs_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[
                activity_header,
                logs_list,
                file_display_widget,
                logs_list_helper_text,
            ],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        logs_wrapper.get_layout().setStretchFactor(activity_header, 0)
        logs_wrapper.get_layout().setStretchFactor(logs_list, 1)
        logs_wrapper.get_layout().setStretchFactor(file_display_widget, 0)
        logs_wrapper.get_layout().setStretchFactor(logs_list_helper_text, 0)

        logs_group_box = GroupBox(
            self,
            layout=QVBoxLayout(),
            widgets=[logs_wrapper],
            title=self.texts.group_title,
        )
        logs_group_box.setObjectName("logs-group-box")

        body = VerticalLayoutWrapper(
            self,
            widgets=[logs_group_box],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body, 1)

        self.ui: LogPanel.UI = LogPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            activity_header=activity_header,
            date_label=date_label,
            event_count_label=event_count_label,
            filter_button=filter_button,
            filter_menu=filter_menu,
            logs_group_box=logs_group_box,
            logs_wrapper=logs_wrapper,
            logs_list=logs_list,
            logs_list_helper_text=logs_list_helper_text,
            file_display_widget=file_display_widget,
        )

        self.setLayout(layout)
        self._seed_placeholder_activities()
        self._render_activities()

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the log panel."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.ui.logs_wrapper.get_layout().setAlignment(
            self.ui.logs_list_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.logs_wrapper.get_layout().setAlignment(
            self.ui.file_display_widget, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.activity_header.layout().setAlignment(
            self.ui.filter_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.logs_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.activity_header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.date_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.event_count_label.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.ui.filter_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.logs_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.logs_group_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.logs_list_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.file_display_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_signals(self) -> None:
        """Connect signals for the log panel and its UI widgets."""
        #### Signals for toggling the log panel visibility ####
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: view_signals.LogPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )
        view_signals.SimulationLogFileUpdated.connect(
            self._on_simulation_log_file_updated
        )
        view_signals.ADBServerStarted.connect(self._on_adb_server_started)
        view_signals.ADBServerStopped.connect(self._on_adb_server_stopped)
        view_signals.AuthentificationSucceeded.connect(
            self._on_authentification_succeeded
        )
        view_signals.AuthentificationFailed.connect(self._on_authentification_failed)
        view_signals.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        view_signals.DeviceSelectionFailed.connect(self._on_device_selection_failed)

        self.ui.logs_list.itemSelectionChanged.connect(
            self._sync_activity_selection_state
        )

    def _build_filter_menu(self, parent: QWidget) -> QMenu:
        """Build a compact category/status filter menu for the activity stream."""
        menu = QMenu(parent)
        menu.setObjectName("activity-log-filter-menu")
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        categories: tuple[ActivityCategory, ...] = (
            "simulation",
            "device",
            "location",
            "adb",
            "file",
            "system",
        )
        levels: tuple[ActivityLevel, ...] = (
            "info",
            "success",
            "warning",
            "error",
            "start",
            "stop",
        )

        self._add_filter_section(menu, "Categories")
        for category in categories:
            action, checkbox = self._add_filter_option(menu, category.title())
            self._category_filter_actions[category] = action
            self._category_filter_widgets[category] = checkbox

        self._add_filter_separator(menu)
        self._add_filter_section(menu, "Status")
        for level in levels:
            action, checkbox = self._add_filter_option(
                menu, ActivityLogItem._LEVEL_LABEL[level]
            )
            self._level_filter_actions[level] = action
            self._level_filter_widgets[level] = checkbox
        return menu

    def _add_filter_section(self, menu: QMenu, text: str) -> None:
        action = QWidgetAction(menu)
        action.setDefaultWidget(ActivityFilterSectionLabel(text, menu))
        menu.addAction(action)

    def _add_filter_separator(self, menu: QMenu) -> None:
        action = QWidgetAction(menu)
        action.setDefaultWidget(ActivityFilterSeparator(menu))
        menu.addAction(action)

    def _add_filter_option(
        self, menu: QMenu, text: str
    ) -> tuple[QWidgetAction, QCheckBox]:
        action = QWidgetAction(menu)
        action.setCheckable(True)
        action.setChecked(True)
        checkbox = ActivityFilterOption(text, menu)
        checkbox.setChecked(True)
        checkbox.toggled.connect(action.setChecked)
        action.toggled.connect(checkbox.setChecked)
        action.toggled.connect(self._on_filter_action_toggled)
        action.setDefaultWidget(checkbox)
        menu.addAction(action)
        return action, checkbox

    def _seed_placeholder_activities(self) -> None:
        """Seed user-facing demo entries until real GUI activity arrives."""
        now = dt.datetime.now().replace(microsecond=0)
        self._activities = [
            ActivityLogEntry(
                id=uuid.uuid4().hex,
                timestamp=now - dt.timedelta(minutes=9),
                category="adb",
                level="info",
                message="ADB bridge ready",
                metadata={"endpoint": "tcp:5037"},
            ),
            ActivityLogEntry(
                id=uuid.uuid4().hex,
                timestamp=now - dt.timedelta(minutes=6),
                category="device",
                level="success",
                message="Device trusted",
                detail="Pixel 8 Pro is available for the location spoofing workflow.",
                metadata={"state": "trusted"},
            ),
            ActivityLogEntry(
                id=uuid.uuid4().hex,
                timestamp=now - dt.timedelta(minutes=3),
                category="location",
                level="info",
                message="Waiting for target location",
                metadata={"source": "map"},
            ),
        ]

    def _visible_activities(self) -> list[ActivityLogEntry]:
        entries = [
            entry
            for entry in self._activities
            if (
                self._category_filter is None or entry.category in self._category_filter
            )
            and (self._level_filter is None or entry.level in self._level_filter)
        ]
        return sorted(entries, key=lambda entry: entry.timestamp, reverse=True)

    def _render_activities(self) -> None:
        """Rebuild the activity list from the session-local entry store."""
        self.ui.logs_list.clear()
        visible_entries = self._visible_activities()
        self._refresh_event_count(len(visible_entries))
        if visible_entries:
            self.ui.date_label.setText(
                _format_activity_date(visible_entries[0].timestamp)
            )
        else:
            self.ui.date_label.setText("Activity")
            return

        grouped_dates = {entry.timestamp.date() for entry in visible_entries}
        show_date_headers = len(grouped_dates) > 1
        current_date: dt.date | None = None
        for entry in visible_entries:
            if show_date_headers and entry.timestamp.date() != current_date:
                current_date = entry.timestamp.date()
                ActivityDateHeaderItem.add_to_list(
                    self.ui.logs_list,
                    _format_activity_date(entry.timestamp),
                )
            ActivityLogItem.add_to_list(self.ui.logs_list, entry)
        self._sync_activity_selection_state()

    def _refresh_event_count(self, visible_count: int) -> None:
        if visible_count == 0:
            self.ui.event_count_label.setText(self.texts.events_empty_count)
        elif visible_count == 1:
            self.ui.event_count_label.setText("1 event")
        else:
            self.ui.event_count_label.setText(f"{visible_count} events")

    def _on_filter_action_toggled(self) -> None:
        selected_categories = {
            category
            for category, action in self._category_filter_actions.items()
            if action.isChecked()
        }
        selected_levels = {
            level
            for level, action in self._level_filter_actions.items()
            if action.isChecked()
        }
        self._category_filter = (
            selected_categories
            if selected_categories != set(self._category_filter_actions)
            else None
        )
        self._level_filter = (
            selected_levels
            if selected_levels != set(self._level_filter_actions)
            else None
        )
        self._render_activities()

    def _sync_activity_selection_state(self) -> None:
        for item in self.ui.logs_list.iter_items():
            if isinstance(item, ActivityLogItem):
                item.set_selected(item.isSelected())

    def _sync_activity_item_size_hints(self) -> None:
        for item in self.ui.logs_list.iter_items():
            if isinstance(item, ActivityLogItem):
                item._sync_size_hint()

    def refresh_layout(self, *, deferred: bool = True) -> None:
        """Refresh list geometry after panel/sidebar visibility changes."""
        if self.layout() is not None:
            self.layout().activate()
        if self.ui.logs_group_box.layout() is not None:
            self.ui.logs_group_box.layout().activate()
        self.ui.logs_list.updateGeometry()
        self.ui.logs_list.doItemsLayout()
        self._sync_activity_item_size_hints()
        self.ui.file_display_widget.refresh_display()
        if deferred:
            QTimer.singleShot(0, lambda: self.refresh_layout(deferred=False))

    def add_activity(
        self,
        message: str,
        category: ActivityCategory,
        level: ActivityLevel = "info",
        detail: str | None = None,
        timestamp: dt.datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Append a user-facing activity entry and return its generated id."""
        if category not in ActivityLogItem._CATEGORY_ICON:
            raise ValueError(f"Unknown activity category: {category}")
        if level not in ActivityLogItem._LEVEL_LABEL:
            raise ValueError(f"Unknown activity level: {level}")
        entry = ActivityLogEntry(
            id=uuid.uuid4().hex,
            timestamp=_coerce_activity_timestamp(timestamp),
            category=category,
            level=level,
            message=message,
            detail=detail,
            metadata={str(key): str(value) for key, value in (metadata or {}).items()},
        )
        self._activities.append(entry)
        self._render_activities()
        return entry.id

    def remove_activity(self, activity_id: str) -> bool:
        """Remove an activity by id.

        Returns:
            True when an entry was removed, False when no entry matched.
        """
        before = len(self._activities)
        self._activities = [
            entry for entry in self._activities if entry.id != activity_id
        ]
        removed = len(self._activities) != before
        if removed:
            self._render_activities()
        return removed

    def clear_activities(self) -> None:
        """Clear all session-local activity entries."""
        self._activities.clear()
        self._render_activities()

    def set_activity_filter(
        self,
        categories: set[ActivityCategory] | list[ActivityCategory] | None = None,
        levels: set[ActivityLevel] | list[ActivityLevel] | None = None,
    ) -> None:
        """Filter visible activity entries by category and/or level."""
        self._category_filter = set(categories) if categories is not None else None
        self._level_filter = set(levels) if levels is not None else None
        self._sync_filter_actions()
        self._render_activities()

    def _sync_filter_actions(self) -> None:
        for category, action in self._category_filter_actions.items():
            checkbox = self._category_filter_widgets[category]
            checked = self._category_filter is None or category in self._category_filter
            action.blockSignals(True)
            checkbox.blockSignals(True)
            action.setChecked(checked)
            checkbox.setChecked(checked)
            checkbox.sync_display()
            checkbox.blockSignals(False)
            action.blockSignals(False)
        for level, action in self._level_filter_actions.items():
            checkbox = self._level_filter_widgets[level]
            checked = self._level_filter is None or level in self._level_filter
            action.blockSignals(True)
            checkbox.blockSignals(True)
            action.setChecked(checked)
            checkbox.setChecked(checked)
            checkbox.sync_display()
            checkbox.blockSignals(False)
            action.blockSignals(False)

    def _on_adb_server_started(self) -> None:
        self.add_activity(
            "ADB server started",
            "adb",
            "success",
            metadata={"state": "running"},
        )

    def _on_adb_server_stopped(self) -> None:
        self.add_activity(
            "ADB server stopped",
            "adb",
            "stop",
            metadata={"state": "idle"},
        )

    def _on_authentification_succeeded(self, device: dict) -> None:
        name = str(device.get("name", "Android device"))
        self.add_activity(
            "Device paired",
            "device",
            "success",
            detail=f"{name} is now trusted by AROW.",
            metadata={"device": name},
        )

    def _on_authentification_failed(
        self, ip: str, port: int, association_code: str
    ) -> None:
        self.add_activity(
            "Pairing failed",
            "device",
            "error",
            detail=f"Could not pair {ip}:{port} with code {association_code}.",
            metadata={"target": f"{ip}:{port}"},
        )

    def _on_device_selection_succeeded(self, device: dict) -> None:
        name = str(device.get("name", "Android device"))
        self.add_activity(
            "Active device selected",
            "device",
            "success",
            metadata={"device": name},
        )

    def _on_device_selection_failed(self, device: dict) -> None:
        name = str(device.get("name", "Android device"))
        self.add_activity(
            "Device selection failed",
            "device",
            "error",
            detail=f"{name} could not be selected for the simulation.",
            metadata={"device": name},
        )

    def is_panel_visible(self) -> bool:
        """Check if the log panel is visible."""
        return bool(self.ui.expand_button.property("toggle"))

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.title.set_leading_icon_path(
            icon_qt_path_for_theme(theme, GenericIcons.LOGS)
        )
        inset = bool(self.ui.expand_button.property("toggle"))
        expand_icon = (
            GenericIcons.LAYOUT_BOTTOMBAR_INSET
            if inset
            else GenericIcons.LAYOUT_BOTTOMBAR
        )
        self.ui.expand_button.set_icon(expand_icon)
        self.ui.expand_button.apply_theme_icons(theme)
        self.ui.filter_button.apply_theme_icons(theme)
        self.ui.file_display_widget.apply_theme_icons(theme)
        for item in self.ui.logs_list.iter_items():
            if isinstance(item, ActivityLogItem):
                item.ui.icon_label.setPixmap(
                    QIcon(
                        icon_qt_path_for_theme(
                            theme, ActivityLogItem._CATEGORY_ICON[item.entry.category]
                        )
                    ).pixmap(
                        QSize(
                            Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
                            Settings.LIST.ACTIVITY_ITEM_ICON_SIZE,
                        )
                    )
                )

    def _on_simulation_log_file_updated(
        self, simulation_id: str, log_file_path: str
    ) -> None:
        """Set the file row from the active simulation's default log path."""
        if not log_file_path:
            return
        path = Path(log_file_path)
        file_name = path.name
        ext = path.suffix.lstrip(".").lower()
        file_type = ext.upper() if ext else "LOG"
        self.ui.file_display_widget.set_file_display(file_name, file_type)
        self._active_simulation_id = simulation_id
        self.add_activity(
            "Simulation log file updated",
            "file",
            "info",
            metadata={"file": file_name},
        )

    def _reduced_height(self) -> int:
        """Height of the panel when reduced (header only): layout padding + header size."""
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        """Show the log panel."""
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        self.refresh_layout()

    def hide_panel(self) -> None:
        """Hide the log panel."""
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR)
            animate_widget_visibility(
                self,
                visible=False,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        self.refresh_layout()

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the log panel."""
        if self.ui.expand_button.property("toggle"):
            # Reduce: hide body and constrain height so the panel under can grow.
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR)
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
            self.ui.expand_button.set_icon(GenericIcons.LAYOUT_BOTTOMBAR_INSET)
            animate_widget_visibility(
                self,
                visible=True,
                axis="vertical",
                collapsed_size=self._reduced_height(),
                content_widget=self.ui.body,
            )
        # Notify parent layout so space is reallocated (panel below gets more height when reduced).
        self.updateGeometry()
        self.refresh_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refresh_layout()
