"""Device-selection blocks."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Final

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from gui import faker as ui_faker
from gui.animation import apply_highlight_level, compute_sine_pulse_level
from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import GroupBox, HelperText, List, PlaceHolder, ToolButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import GridLayoutWrapper, HorizontalLayoutWrapper
from logger import logger

from gui.blocks.device.device_item import DeviceItem


class DeviceSelectionBlock(QFrame, Block):
    """Available-device list block used by the device selection panel."""

    @dataclass(frozen=True)
    class Text:
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
        available_device_list: List
        available_device_empty_state: PlaceHolder
        available_device_wrapper: HorizontalLayoutWrapper
        available_device_group_box: GroupBox
        add_device_button: ToolButton
        refresh_button: ToolButton
        buttons_wrapper: GridLayoutWrapper
        select_helper_text: HelperText

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._device_item_type = DeviceItem
        self.texts = DeviceSelectionBlock.Text()

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.SPACING.XS)

        available_device_list = List(None)
        available_device_list.setObjectName("available-device-list")
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
        layout.addWidget(available_device_group_box)
        layout.setStretchFactor(available_device_group_box, 1)
        self.setLayout(layout)

        self.ui = DeviceSelectionBlock.UI(
            available_device_list=available_device_list,
            available_device_empty_state=available_device_empty_state,
            available_device_group_box=available_device_group_box,
            available_device_wrapper=available_device_wrapper,
            add_device_button=add_device_button,
            refresh_button=refresh_button,
            buttons_wrapper=buttons_wrapper,
            select_helper_text=select_helper_text,
        )

        available_device_list.viewport().installEventFilter(self)

        self._highlight_pulse_timer = QTimer(self)
        self._highlight_pulse_timer.setSingleShot(False)
        self._highlight_pulse_timer.timeout.connect(self._on_highlight_pulse_tick)
        self._highlight_stop_timer = QTimer(self)
        self._highlight_stop_timer.setSingleShot(True)
        self._highlight_stop_timer.timeout.connect(self.stop_highlight_attention)
        self._highlight_elapsed = QElapsedTimer()

        self._finalize_ui_hooks()
        self._update_available_device_empty_state_visibility()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.ui.available_device_list.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._reposition_available_device_empty_state()
            self._sync_available_device_item_size_hints()
        return super().eventFilter(watched, event)

    def _set_alignment(self) -> None:
        self.ui.available_device_group_box.layout().setAlignment(
            self.ui.select_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.available_device_wrapper.get_layout().setAlignment(
            self.ui.buttons_wrapper,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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

    def _connect_signals(self) -> None:
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

        model = self.ui.available_device_list.model()
        model.rowsInserted.connect(self._on_available_device_list_model_changed)
        model.rowsRemoved.connect(self._on_available_device_list_model_changed)
        model.modelReset.connect(self._on_available_device_list_model_changed)
        model.layoutChanged.connect(self._on_available_device_list_model_changed)
        model.dataChanged.connect(self._on_available_device_list_model_changed)

    def refresh_last_communication_timestamps(
        self, *, now: dt.datetime | None = None
    ) -> None:
        ref = now if now is not None else dt.datetime.now()
        for list_item in self.ui.available_device_list.iter_items():
            if isinstance(list_item, self._device_item_type):
                list_item.refresh_last_communication_label(now=ref)

    def _reposition_available_device_empty_state(self) -> None:
        viewport = self.ui.available_device_list.viewport()
        placeholder = self.ui.available_device_empty_state
        inset = Settings.SPACING.XS
        geometry = viewport.rect().adjusted(inset, inset, -inset, -inset)
        placeholder.setGeometry(geometry)
        min_side = max(0, min(geometry.width(), geometry.height()))
        icon_size = max(24, min(Settings.PLACEHOLDER.ICON_SIZE, int(min_side * 0.38)))
        placeholder.ui.svg.setFixedSize(icon_size, icon_size)
        placeholder.raise_()

    def _update_available_device_empty_state_visibility(self) -> None:
        is_empty = self.ui.available_device_list.count() == 0
        self.ui.available_device_empty_state.setVisible(is_empty)
        if is_empty:
            self._reposition_available_device_empty_state()

    def _on_available_device_list_model_changed(self, *args) -> None:
        self._update_available_device_empty_state_visibility()
        self._sync_available_device_selection_state()
        self._sync_available_device_item_size_hints()

    def _sync_available_device_selection_state(self) -> None:
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item.set_selected(item.isSelected())

    def _sync_available_device_item_size_hints(self) -> None:
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item._sync_size_hint()

    def _on_authentification_succeeded(self, device: dict) -> None:
        for item in self.ui.available_device_list.iter_items():
            item.badge = "trusted"
        item = self._device_item_type.add_to_list(
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

    def _on_device_selected(self, item) -> None:
        if item is None:
            return
        view_signals.DeviceSelectionRequested.emit(item.id, item.name)

    def _on_device_selection_succeeded(self, device: dict) -> None:
        selected_item = self.ui.available_device_list.currentItem()
        if selected_item is None:
            return
        for list_item in self.ui.available_device_list.iter_items():
            list_item.badge = "trusted"
        selected_item.badge = "active"
        self._on_available_device_list_model_changed()

    def _on_device_selection_failed(self, device: dict) -> None:
        self.ui.available_device_list.setCurrentItem(None)
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_devices_updated(self, devices: list[dict]) -> None:
        self.ui.available_device_list.clear()
        for device in devices:
            self._device_item_type.add_to_list(
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
        logger.info("Available device list refresh requested.")
        view_signals.RefreshDeviceListRequested.emit()

    def _on_remove_device_requested(self, id: str) -> None:
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

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.available_device_empty_state.apply_theme_icons(theme)
        self.ui.add_device_button.apply_theme_icons(theme)
        self.ui.refresh_button.apply_theme_icons(theme)
        for lw_item in self.ui.available_device_list.iter_items():
            if isinstance(lw_item, self._device_item_type):
                lw_item.apply_theme_icons(theme)

    def _on_highlight_pulse_tick(self) -> None:
        cycle_ms = Settings.ANIMATION.ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS
        elapsed = self._highlight_elapsed.elapsed()
        level = compute_sine_pulse_level(elapsed, cycle_ms)
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", level
        )

    def start_highlight_attention(self) -> None:
        self.stop_highlight_attention()
        self._highlight_elapsed.start()
        self._highlight_pulse_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_UPDATE_MS
        )
        self._highlight_stop_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_DURATION
        )

    def stop_highlight_attention(self) -> None:
        self._highlight_pulse_timer.stop()
        self._highlight_stop_timer.stop()
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", 0
        )

    def add_list_items_placeholder(self) -> None:
        self._device_item_type.add_to_list(
            self.ui.available_device_list,
            id=self.texts.placeholder_primary_device_id,
            text=self.texts.placeholder_primary_device,
            type="available",
            device_kind="mobile",
            badge="trusted",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_primary,
            last_communication=self.texts.placeholder_last_communication_active,
        )
        self._device_item_type.add_to_list(
            self.ui.available_device_list,
            id=self.texts.placeholder_secondary_device_id,
            text=self.texts.placeholder_secondary_device,
            type="available",
            device_kind="mobile",
            badge="trusted",
            operating_system=self.texts.placeholder_operating_system,
            location=self.texts.placeholder_location_primary,
            last_communication=self.texts.placeholder_last_communication_recent,
        )
        self._device_item_type.add_to_list(
            self.ui.available_device_list,
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
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item.extend_device_item()

    def shorten_list_items(self) -> None:
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item.shorten_device_item()

    def current_item(self):
        return self.ui.available_device_list.currentItem()

    def device_list(self) -> List:
        return self.ui.available_device_list
