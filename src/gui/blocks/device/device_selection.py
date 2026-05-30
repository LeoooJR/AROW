"""Device-selection blocks."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Final

from PySide6.QtCore import (
    QElapsedTimer,
    QEvent,
    QItemSelectionModel,
    QObject,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from gui import faker as ui_faker
from gui.animation import apply_highlight_level, compute_sine_pulse_level
from gui.blocks.base import Block
from gui.blocks.device.device_empty_state import DeviceEmptyState
from gui.blocks.device.device_item import DeviceItem
from gui.colors import Theme
from gui.components import GroupBox, HelperText, List, ToolButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import GridLayoutWrapper, HorizontalLayoutWrapper
from logger import logger


class DeviceSelectionBlock(QFrame, Block):
    """Available-device list block used by the device selection panel."""

    @dataclass(frozen=True)
    class Text:
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
        available_device_empty_state: DeviceEmptyState
        available_device_wrapper: HorizontalLayoutWrapper
        available_device_group_box: GroupBox
        add_device_button: ToolButton
        refresh_button: ToolButton
        buttons_wrapper: GridLayoutWrapper
        select_helper_text: HelperText

    def __init__(self, parent: QWidget | None = None):
        """Build the available-device list block and its action controls."""
        super().__init__(parent)

        self._device_item_type = DeviceItem
        self.texts = DeviceSelectionBlock.Text()

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(Settings.SPACING.XS)

        available_device_list = List(None)
        available_device_list.setObjectName("available-device-list")
        available_device_empty_state = DeviceEmptyState(available_device_list.viewport())
        available_device_empty_state.setObjectName("available-device-empty-state")
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
        self._highlight_stop_timer.timeout.connect(self._stop_highlight_attention)
        self._highlight_elapsed = QElapsedTimer()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(False)
        self._refresh_timer.timeout.connect(self._on_refresh_timer_tick)
        self._refresh_timer.setInterval(Settings.LIST.REFRESH_MS)
        self._refresh_timer.start()

        self.ui.available_device_list.selectionModel().clear()  # Clear the selection model to avoid any residual selection when the list is empty.
        self._has_active_device = False
        self._is_extended = False

        self._finalize_ui_hooks()
        self._update_available_device_empty_state_visibility()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Keep placeholder geometry and row hints synced with list viewport events."""
        if watched is self.ui.available_device_list.viewport() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._reposition_available_device_empty_state()
            self._sync_available_device_item_size_hints()
        return super().eventFilter(watched, event)

    def _set_alignment(self) -> None:
        """Align helper text and action buttons inside the device group box."""
        self.ui.available_device_group_box.layout().setAlignment(
            self.ui.select_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.available_device_wrapper.get_layout().setAlignment(
            self.ui.buttons_wrapper,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

    def _set_size_policy(self) -> None:
        """Set resize behavior for the list, wrapper, group box, and helper text."""
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
        """Wire device list actions, selection events, and model-change refresh hooks."""

        #### Signals for handling the device list actions ####
        self.ui.add_device_button.clicked.connect(view_signals.AddDeviceRequested.emit)
        self.ui.refresh_button.clicked.connect(self._on_refresh_button_clicked)
        self.ui.available_device_list.itemClicked.connect(self._on_device_selected)
        self.ui.available_device_list.itemSelectionChanged.connect(
            self._sync_available_device_selection_state
        )
        view_signals.RemoveDeviceRequested.connect(self._on_remove_device_requested)

        #### Signals for handling the device selection panel visibility requests ####
        view_signals.ExtendDeviceSelectionPanelRequested.connect(self.extend)
        view_signals.ShortenDeviceSelectionPanelRequested.connect(self.shorten)

        #### Signals for handling the authentification / selection workflow ####
        view_signals.AuthentificationSucceeded.connect(
            self._on_authentification_succeeded
        )
        view_signals.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        view_signals.DeviceSelectionFailed.connect(self._on_device_selection_failed)
        view_signals.DevicesUpdated.connect(self._on_devices_updated)

        #### Signals for handling the UI constraints disabled ####
        view_signals.UiConstraintsDisabled.connect(self._on_ui_constraints_disabled)

        #### Signals for handling the device list model changes ####
        model = self.ui.available_device_list.model()
        model.rowsInserted.connect(self._on_available_device_list_model_changed)
        model.rowsRemoved.connect(self._on_available_device_list_model_changed)
        model.modelReset.connect(self._on_available_device_list_model_changed)
        model.layoutChanged.connect(self._on_available_device_list_model_changed)
        model.dataChanged.connect(self._on_available_device_list_model_changed)

        #### Signals for handling the helper animation requests ####
        view_signals.RunHelperAnimationRequested.connect(self._on_run_helper_animation)
        view_signals.MapTabActivated.connect(self._on_map_tab_activated)

    def _on_ui_constraints_disabled(self) -> None:
        """Seed placeholder rows when UI constraints are disabled."""
        self.add_list_items_placeholder()

    def _on_refresh_timer_tick(self, *, now: dt.datetime | None = None) -> None:
        """Refresh live last-communication labels on every device row."""
        ref = now if now is not None else dt.datetime.now()
        for list_item in self.ui.available_device_list.iter_items():
            if isinstance(list_item, self._device_item_type):
                list_item.refresh_last_communication_label(now=ref)
                list_item.refresh_badge(now=ref)

    def _reposition_available_device_empty_state(self) -> None:
        """Resize and center the empty-state placeholder over the list viewport."""
        viewport = self.ui.available_device_list.viewport()
        placeholder = self.ui.available_device_empty_state
        inset = Settings.SPACING.XS
        available_geometry = viewport.rect().adjusted(inset, inset, -inset, -inset)
        card_width = min(
            Settings.LIST.DEVICE_EMPTY_STATE_WIDTH,
            available_geometry.width(),
        )
        card_x = available_geometry.x() + (
            (available_geometry.width() - card_width) // 2
        )
        placeholder.fit_to_available_width(card_width)
        placeholder.setGeometry(
            card_x,
            available_geometry.y(),
            card_width,
            available_geometry.height(),
        )
        placeholder.raise_()

    def _update_available_device_empty_state_visibility(self) -> None:
        """Show the empty-state placeholder only when the device list is empty."""
        is_empty = self.ui.available_device_list.count() == 0
        self.ui.available_device_empty_state.setVisible(is_empty)
        self.ui.select_helper_text.setVisible(not is_empty)
        self.ui.buttons_wrapper.setVisible(not is_empty)
        if is_empty:
            self._reposition_available_device_empty_state()

    def _on_available_device_list_model_changed(self, *args) -> None:
        """Refresh placeholder, selection styling, and row sizes after list changes."""
        self._update_available_device_empty_state_visibility()
        self._sync_available_device_item_presentation_state()
        self._sync_available_device_selection_state()
        self._sync_available_device_item_size_hints()

    def _sync_available_device_item_presentation_state(self) -> None:
        """Apply the block's current compact/extended mode to every device row."""
        for item in self.ui.available_device_list.iter_items():
            if not isinstance(item, self._device_item_type):
                continue
            if self._is_extended:
                item.extend()
            else:
                item.shorten()

    def _sync_available_device_selection_state(self) -> None:
        """Mirror QListWidget selection state onto each custom device row widget."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item.set_selected(item.isSelected())

    def _sync_available_device_item_size_hints(self) -> None:
        """Recalculate custom row size hints after width or content changes."""
        for item in self.ui.available_device_list.iter_items():
            if isinstance(item, self._device_item_type):
                item._sync_size_hint()

    def _on_authentification_succeeded(self, device: dict) -> None:
        """Add a newly authenticated device and mark it as the active selection."""
        self._has_active_device = (
            False  # Authentification does not mean the device is active.
        )
        item = self._device_item_type.add_to_list(
            self.ui.available_device_list,
            id=device["id"],
            text=device["name"],
            type="available",
            badge="new",
            operating_system=device["os"],
            location="N/A",
            last_communication=device["last_communication"],
            alert_highlight=True,
        )
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_device_selected(self, item) -> None:
        """Request selection of the clicked device item."""
        if item is None:
            return
        if isinstance(item, self._device_item_type):
            view_signals.DeviceSelectionRequested.emit(item.id, item.name)
        else:
            logger.warning(
                "DeviceSelectionBlock: device item is not a DeviceItem", item=item
            )

    def _on_device_selection_succeeded(self, device: dict) -> None:
        """Mark the currently selected row active after selection succeeds."""
        self._has_active_device = True
        selected_item = self.ui.available_device_list.currentItem()
        if selected_item is None:
            return
        # Ensure that no other device is active.
        for list_item in self.ui.available_device_list.iter_items():
            if list_item.badge == "active":
                list_item.badge = "trusted"
                break
        # Mark the selected device as active.
        selected_item.badge = "active"
        # Refresh the device list.
        self._on_available_device_list_model_changed()

    def _on_device_selection_failed(self, device: dict) -> None:
        """Clear the current row selection after selection failure."""
        self._has_active_device = False
        self.ui.available_device_list.setCurrentItem(
            None, QItemSelectionModel.SelectionFlag.Clear
        )
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def _on_devices_updated(self, devices: list[dict]) -> None:
        """Replace the available-device list from controller-provided device data."""
        self._has_active_device = False
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
        """Emit a device-list refresh request from the refresh action button."""
        logger.info("Available device list refresh requested.")
        view_signals.RefreshDeviceListRequested.emit()

    def _on_remove_device_requested(self, id: str) -> None:
        """Remove the matching device row when a row-level delete action is requested.
        id: The id of the device to remove.
        """
        logger.info("Remove device requested.", id=id)
        current_item_before_removal = self.ui.available_device_list.currentItem()
        for item_index, item in enumerate(
            self.ui.available_device_list.iter_items(), start=0
        ):
            if isinstance(item, self._device_item_type) and item.id == id:
                removed_item: DeviceItem = self.ui.available_device_list.takeItem(
                    item_index
                )
                if removed_item is not None:
                    if (
                        removed_item == current_item_before_removal
                    ):  # The removed item was the current item
                        self._has_active_device = False
                        self.ui.available_device_list.setCurrentItem(
                            None, QItemSelectionModel.SelectionFlag.Clear
                        )
                    del removed_item
                    break
        self.ui.available_device_list.sortItems()
        self._on_available_device_list_model_changed()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh empty-state, action-button, and row icons for the active theme."""
        self.ui.available_device_empty_state.apply_theme_icons(theme)
        self.ui.add_device_button.apply_theme_icons(theme)
        self.ui.refresh_button.apply_theme_icons(theme)
        for lw_item in self.ui.available_device_list.iter_items():
            if isinstance(lw_item, self._device_item_type):
                lw_item.apply_theme_icons(theme)

    def _on_highlight_pulse_tick(self) -> None:
        """Advance the transient attention pulse on the available-device list."""
        cycle_ms = Settings.ANIMATION.ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS
        elapsed = self._highlight_elapsed.elapsed()
        level = compute_sine_pulse_level(elapsed, cycle_ms)
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", level
        )

    def _is_block_visible_to_user(self) -> bool:
        """Return whether the left sidebar ancestor chain is visible to the user."""
        widget = self.parentWidget()
        while widget is not None:
            if widget.objectName() == "left-panels-wrapper":
                return widget.isVisible()
            widget = widget.parentWidget()
        return self.isVisible()

    def _should_run_device_attention_highlight(self) -> bool:
        """True when the list is shown and no device row is selected yet."""
        if not self._is_block_visible_to_user():
            return False
        if not self.ui.available_device_list.isVisible():
            return False
        if self.ui.available_device_list.currentItem() is not None:
            return False
        if self._has_active_device:
            return False
        return True

    def _on_run_helper_animation(self) -> None:
        """Start attention pulse when idle helper is requested and guards pass."""
        if not self._should_run_device_attention_highlight():
            return
        self._start_highlight_attention()

    def _on_map_tab_activated(self) -> None:
        """Start attention pulse when the Map tab is activated and guards pass."""
        if not self._should_run_device_attention_highlight():
            return
        self._start_highlight_attention()

    def _start_highlight_attention(self) -> None:
        """Start the attention pulse and set the list highlight level."""
        self._stop_highlight_attention()
        self._highlight_elapsed.start()
        self._highlight_pulse_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_UPDATE_MS
        )
        self._highlight_stop_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_DURATION
        )

    def _stop_highlight_attention(self) -> None:
        """Stop the attention pulse and reset the list highlight level."""
        self._highlight_pulse_timer.stop()
        self._highlight_stop_timer.stop()
        apply_highlight_level(
            self.ui.available_device_list, "device-list-highlight-level", 0
        )

    def add_list_items_placeholder(self) -> None:
        """Seed fake device rows for unconstrained/offscreen UI demonstrations."""
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

    def extend(self) -> None:
        """Expand all device rows to show extended metadata and actions."""
        self._is_extended = True
        self._sync_available_device_item_presentation_state()

    def shorten(self) -> None:
        """Collapse all device rows back to their compact presentation."""
        self._is_extended = False
        self._sync_available_device_item_presentation_state()

    @property
    def available_device_list(self) -> List:
        """Return the available-device list widget."""
        return self.ui.available_device_list
