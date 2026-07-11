"""Milestone target block for the location side panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Real
from typing import Final

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui import faker as ui_faker
from gui.blocks.base import Block
from gui.blocks.location.location_settings import location_settings
from gui.colors import Theme
from gui.components import Button, StatusBadge
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import (
    GridLayoutWrapper,
    HorizontalLayoutWrapper,
    VerticalLayoutWrapper,
)


class MilestoneMetadataItem(HorizontalLayoutWrapper):
    """Compact key/value display for milestone metadata."""

    texts: MilestoneMetadataItem.Text
    ui: MilestoneMetadataItem.UI

    @dataclass(frozen=True)
    class Text:
        key: str
        value: str = "--"

    @dataclass
    class UI:
        key: QLabel
        value: QLabel

    def __init__(
        self,
        parent: QWidget | None,
        *,
        key: str,
        value: str = "--",
    ) -> None:
        item_texts = MilestoneMetadataItem.Text(key=key, value=value)

        key_label = QLabel(key, parent)
        key_label.setProperty("milestone-metadata-key", True)

        value_label = QLabel(value, parent)
        value_label.setProperty("milestone-metadata-value", True)
        value_label.setWordWrap(False)

        super().__init__(
            parent,
            widgets=[key_label, value_label],
            spacing=location_settings.METADATA_KEY_VALUE_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        self.setObjectName("milestone-metadata-item")
        self.setProperty("milestone-metadata-item", True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._raw_value = _display_value(value)
        self._pending_value_elision_refresh = False
        self.texts = item_texts
        self.ui = MilestoneMetadataItem.UI(key=key_label, value=value_label)
        self.ui.key.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        self.ui.value.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.ui.value.setMinimumWidth(0)
        self.ui.key.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.ui.value.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.get_layout().setStretchFactor(key_label, 0)
        self.get_layout().setStretchFactor(value_label, 1)

    def set_value(self, value: object | None) -> None:
        """Update the displayed value, falling back to ``--`` for empty data."""
        display_value = _display_value(value)
        self._raw_value = display_value
        self.texts = MilestoneMetadataItem.Text(key=self.texts.key, value=display_value)
        self.ui.value.setText(display_value)
        self._schedule_value_elision_refresh()

    def resizeEvent(self, event) -> None:
        """Keep long values elided whenever the metadata item width changes."""
        super().resizeEvent(event)
        self._schedule_value_elision_refresh()

    @property
    def raw_value(self) -> str:
        """Return the unelided displayed value."""
        return self._raw_value

    @Slot()
    def _refresh_value_elision(self) -> None:
        """Render the raw value with right-side elision inside the available width."""
        self._pending_value_elision_refresh = False
        try:
            available_width = max(0, self.ui.value.width())
        except RuntimeError:
            return
        if available_width <= 0:
            self.ui.value.setText(self._raw_value)
            return
        elided = QFontMetrics(self.ui.value.font()).elidedText(
            self._raw_value,
            Qt.TextElideMode.ElideRight,
            available_width,
        )
        self.ui.value.setText(elided)
        self.ui.value.setToolTip(self._raw_value if elided != self._raw_value else "")

    def _schedule_value_elision_refresh(self) -> None:
        """Refresh elision after Qt has settled child label geometry."""
        if self._pending_value_elision_refresh:
            return
        self._pending_value_elision_refresh = True
        QTimer.singleShot(0, self._refresh_value_elision)


class MilestoneTargetBlock(VerticalLayoutWrapper, Block):
    """Location panel block summarizing the selected milestone target."""

    texts: MilestoneTargetBlock.Text
    ui: MilestoneTargetBlock.UI

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Milestone target"
        default_status: Final[str] = "Not set"
        default_status_kind: Final[str] = "not-set"
        target_button: Final[str] = "Set target"
        line_key: Final[str] = "Line"
        km_key: Final[str] = "KM"
        longitude_key: Final[str] = "Longitude"
        latitude_key: Final[str] = "Latitude"
        type_key: Final[str] = "Type"
        source_key: Final[str] = "Source"
        placeholder_line: str = field(
            default_factory=ui_faker.generate_milestone_line_label
        )
        placeholder_km: str = field(
            default_factory=ui_faker.generate_milestone_km_label
        )
        placeholder_longitude: float = field(
            default_factory=ui_faker.generate_milestone_longitude
        )
        placeholder_latitude: float = field(
            default_factory=ui_faker.generate_milestone_latitude
        )
        placeholder_type: str = field(
            default_factory=ui_faker.generate_milestone_type_label
        )
        placeholder_source: str = field(
            default_factory=ui_faker.generate_milestone_source_label
        )

    @dataclass
    class UI:
        header: HorizontalLayoutWrapper
        title: QLabel
        status_badge: StatusBadge
        metadata_grid: GridLayoutWrapper
        line_item: MilestoneMetadataItem
        km_item: MilestoneMetadataItem
        longitude_item: MilestoneMetadataItem
        latitude_item: MilestoneMetadataItem
        type_item: MilestoneMetadataItem
        source_item: MilestoneMetadataItem
        footer: HorizontalLayoutWrapper
        target_button: Button

    def __init__(self, parent: QWidget | None = None) -> None:
        block_texts = MilestoneTargetBlock.Text()

        title = QLabel(block_texts.title, parent)
        title.setProperty("welcome-section-title", True)

        status_badge = StatusBadge(
            parent,
            text=block_texts.default_status,
            kind=block_texts.default_status_kind,
        )

        header = HorizontalLayoutWrapper(
            parent,
            widgets=[title, status_badge],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        header.setObjectName("milestone-target-header")
        header.get_layout().setStretchFactor(title, 1)
        header.get_layout().setAlignment(status_badge, Qt.AlignmentFlag.AlignRight)

        line_item = MilestoneMetadataItem(parent, key=block_texts.line_key)
        km_item = MilestoneMetadataItem(parent, key=block_texts.km_key)
        longitude_item = MilestoneMetadataItem(parent, key=block_texts.longitude_key)
        latitude_item = MilestoneMetadataItem(parent, key=block_texts.latitude_key)
        type_item = MilestoneMetadataItem(parent, key=block_texts.type_key)
        source_item = MilestoneMetadataItem(parent, key=block_texts.source_key)

        metadata_grid = GridLayoutWrapper(
            parent,
            widgets=[],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        metadata_grid.setObjectName("milestone-metadata-grid")
        metadata_grid.get_layout().addWidget(line_item, 0, 0)
        metadata_grid.get_layout().addWidget(longitude_item, 1, 0)
        metadata_grid.get_layout().addWidget(type_item, 2, 0)
        metadata_grid.get_layout().addWidget(km_item, 0, 1)
        metadata_grid.get_layout().addWidget(latitude_item, 1, 1)
        metadata_grid.get_layout().addWidget(source_item, 2, 1)
        metadata_grid.get_layout().setHorizontalSpacing(
            location_settings.METADATA_GRID_HORIZONTAL_SPACING
        )
        metadata_grid.get_layout().setVerticalSpacing(
            location_settings.METADATA_GRID_VERTICAL_SPACING
        )
        metadata_grid.get_layout().setColumnStretch(0, 1)
        metadata_grid.get_layout().setColumnStretch(1, 1)
        for row in range(3):
            metadata_grid.get_layout().setRowStretch(row, 1)

        target_button = Button(
            parent,
            block_texts.target_button,
            icon=GenericIcons.CROSSHAIR,
            theme_unresponsive=True,
        )
        target_button.setObjectName("location-target-button")
        target_button.setProperty("location-target-button", True)
        target_button.setText(f" {block_texts.target_button}")

        footer = HorizontalLayoutWrapper(
            parent,
            widgets=[target_button],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_beginning=True,
        )
        footer.setObjectName("milestone-target-footer")

        super().__init__(
            parent,
            widgets=[header, metadata_grid, footer],
            spacing=location_settings.TARGET_BLOCK_SPACING,
            margins=(
                location_settings.TARGET_PADDING_LEFT,
                location_settings.TARGET_PADDING_TOP,
                location_settings.TARGET_PADDING_RIGHT,
                location_settings.TARGET_PADDING_BOTTOM,
            ),
        )
        self.setObjectName("milestone-target-block")
        self.setProperty("milestone-target-block", True)
        self.texts = block_texts
        self.ui = MilestoneTargetBlock.UI(
            header=header,
            title=title,
            status_badge=status_badge,
            metadata_grid=metadata_grid,
            line_item=line_item,
            km_item=km_item,
            longitude_item=longitude_item,
            latitude_item=latitude_item,
            type_item=type_item,
            source_item=source_item,
            footer=footer,
            target_button=target_button,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.metadata_grid.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.footer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.target_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        self.get_layout().setAlignment(
            self.ui.footer, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom
        )
        self.get_layout().setStretchFactor(self.ui.header, 0)
        self.get_layout().setStretchFactor(self.ui.metadata_grid, 1)
        self.get_layout().setStretchFactor(self.ui.footer, 0)

    def _connect_signals(self) -> None:
        self.ui.target_button.clicked.connect(signals.UI.TargetSelectionRequested.emit)
        signals.UI.UiConstraintsDisabled.connect(self._on_ui_constraints_disabled)
        signals.DEVICE.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        signals.DEVICE.RemoveActiveDeviceSucceeded.connect(
            self._on_remove_active_device_succeeded
        )
        signals.SIMULATION.SimulationLocationValidated.connect(
            self._on_simulation_location_validated
        )

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.target_button.apply_theme_icons(theme)

    def set_target_values(
        self,
        *,
        line: object | None = None,
        km: object | None = None,
        longitude: object | None = None,
        latitude: object | None = None,
        type_: object | None = None,
        source: object | None = None,
        status_text: str | None = None,
        status_kind: str | None = None,
    ) -> None:
        """Update displayed milestone values and optional status badge."""
        updates: tuple[tuple[object | None, MilestoneMetadataItem], ...] = (
            (line, self.ui.line_item),
            (km, self.ui.km_item),
            (_coordinate_display_value(longitude), self.ui.longitude_item),
            (_coordinate_display_value(latitude), self.ui.latitude_item),
            (type_, self.ui.type_item),
            (source, self.ui.source_item),
        )
        for value, item in updates:
            item.set_value(value)

        if status_text is not None or status_kind is not None:
            self.ui.status_badge.set_status(
                status_text or self.ui.status_badge.text(),
                status_kind or self.ui.status_badge.kind(),
            )

    def clear_target_values(self) -> None:
        """Clear the target values."""
        self.set_target_values(
            line=None,
            km=None,
            longitude=None,
            latitude=None,
            type_=None,
            source=None,
            status_text=self.texts.default_status,
            status_kind=self.texts.default_status_kind,
        )

    ### Slots ###

    @Slot()
    def _on_ui_constraints_disabled(self) -> None:
        """Re-apply placeholder values when UI constraints are disabled."""
        self.set_placeholder_values()

    @Slot(str, int, str, int, float, float, str)
    def _on_simulation_location_validated(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        latitude: float,
        longitude: float,
        label: str,
    ) -> None:
        """Update the milestone target block when a simulation location is validated."""
        _ = simulation_id
        self.set_target_values(
            line=f"{line_code}-{line_troncon}",
            km=km,
            latitude=latitude,
            longitude=longitude,
            type_=label,
            source=None,
            status_text="Ready",
            status_kind="ready",
        )

    @Slot(str, str, str)
    def _on_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        """Update the milestone target block when a device selection succeeds."""
        self.clear_target_values()

    @Slot(str)
    def _on_remove_active_device_succeeded(self, device_id: str) -> None:
        """Update the milestone target block when the active device is removed."""
        self.clear_target_values()

    def set_placeholder_values(self) -> None:
        """Populate the block with generated placeholder milestone values."""
        self.set_target_values(
            line=self.texts.placeholder_line,
            km=self.texts.placeholder_km,
            longitude=self.texts.placeholder_longitude,
            latitude=self.texts.placeholder_latitude,
            type_=self.texts.placeholder_type,
            source=self.texts.placeholder_source,
            status_text="Ready",
            status_kind="ready",
        )


def _display_value(value: object | None) -> str:
    """Format empty values as the shared placeholder."""
    if value is None:
        return "--"
    text = str(value).strip()
    return text if text else "--"


def _coordinate_display_value(value: object | None) -> str | None:
    """Format coordinate values to a bounded precision for compact display."""
    if value is None:
        return None
    if isinstance(value, Real) and not isinstance(value, bool):
        return f"{float(value):.6f}"
    display_value = _display_value(value)
    if display_value == "--":
        return display_value
    try:
        return f"{float(display_value):.6f}"
    except ValueError:
        return display_value
