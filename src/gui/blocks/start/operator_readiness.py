"""Welcome operator-readiness block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.blocks.start.start_settings import start_settings
from gui.colors import Theme
from gui.components import StatusBadge
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class ReadinessRow(HorizontalLayoutWrapper):
    """Compact operator-readiness status row."""

    texts: ReadinessRow.Text
    ui: ReadinessRow.UI

    @dataclass(frozen=True)
    class Text:
        label: str
        detail: str
        status: str

    @dataclass
    class UI:
        label: QLabel
        detail: QLabel
        status: StatusBadge
        text_wrapper: VerticalLayoutWrapper

    def __init__(
        self,
        parent: QWidget | None,
        *,
        label: str,
        detail: str,
        status: str,
        status_kind: str = "muted",
    ) -> None:
        self.texts = ReadinessRow.Text(label=label, detail=detail, status=status)

        label_widget = QLabel(label, parent)
        label_widget.setObjectName("readiness-row-label")
        label_widget.setProperty("readiness-row-label", True)

        detail_widget = QLabel(detail, parent)
        detail_widget.setObjectName("readiness-row-detail")
        detail_widget.setProperty("readiness-row-detail", True)
        detail_widget.setWordWrap(False)
        width = max(1, detail_widget.contentsRect().width())
        elided = QFontMetrics(detail_widget.font()).elidedText(
            detail, Qt.TextElideMode.ElideRight, width
        )
        detail_widget.setText(elided)

        text_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[label_widget, detail_widget],
            spacing=2,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        text_wrapper.setObjectName("readiness-row-text")

        status_widget = StatusBadge(
            parent,
            text=status,
            kind=status_kind,
            object_name="readiness-status-chip",
            property_name="readiness-status-chip",
        )

        super().__init__(
            parent,
            widgets=[text_wrapper, status_widget],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_SMALL,
        )
        self.setObjectName("readiness-row")
        self.setProperty("readiness-row", True)
        self.ui = ReadinessRow.UI(
            label=label_widget,
            detail=detail_widget,
            status=status_widget,
            text_wrapper=text_wrapper,
        )
        self.get_layout().setStretchFactor(text_wrapper, 1)
        self.get_layout().setAlignment(status_widget, Qt.AlignmentFlag.AlignVCenter)

    def update(
        self, label: str, detail: str, status: str, status_kind: str = "muted"
    ) -> None:
        """Update the readiness row."""
        self._set_label(label)
        self._set_detail(detail)
        self._set_status(status, status_kind)

    def _set_label(self, label: str) -> None:
        """Update the label label."""
        self.ui.label.setText(label)

    def _set_detail(self, detail: str) -> None:
        """Update the detail label."""
        self.ui.detail.setText(detail)

    def _set_status(self, status: str, status_kind: str = "muted") -> None:
        """Update the status label."""
        self.ui.status.set_status(status, status_kind)


class OperatorReadinessBlock(VerticalLayoutWrapper, Block):
    """Welcome card summarizing operator workflow readiness."""

    texts: OperatorReadinessBlock.Text
    ui: OperatorReadinessBlock.UI

    ROWS_INDEX_MAPPING: dict[str, int] = {
        "host": 0,
        "device": 1,
        "location": 2,
        "simulation": 3,
    }

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Operator readiness"
        default_rows: tuple[tuple[str, str, str, str], ...] = (
            ("Host", "ADB bridge booting up", "PENDING", "ready"),
            ("Device link", "Awaiting trusted Android target", "PENDING", "muted"),
            ("Location set", "Railway milestone not assigned", "PENDING", "muted"),
            (
                "Simulation armed",
                "Start locked until target is selected",
                "LOCKED",
                "muted",
            ),
        )

    @dataclass
    class UI:
        title: QLabel
        rows_wrapper: VerticalLayoutWrapper
        rows: list[ReadinessRow]

    def __init__(self, parent: QWidget | None = None) -> None:
        block_texts = OperatorReadinessBlock.Text()

        title = QLabel(block_texts.title, parent)
        title.setProperty("welcome-section-title", True)

        row_widgets = [
            ReadinessRow(
                parent,
                label=label,
                detail=detail,
                status=status,
                status_kind=status_kind,
            )
            for label, detail, status, status_kind in block_texts.default_rows
        ]
        rows_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=row_widgets,
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        rows_wrapper.setObjectName("readiness-rows-wrapper")

        super().__init__(
            parent,
            widgets=[title, rows_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                start_settings.CARD_PADDING_LEFT,
                start_settings.CARD_PADDING_TOP,
                start_settings.CARD_PADDING_RIGHT,
                start_settings.CARD_PADDING_BOTTOM,
            ),
        )
        self.setObjectName("welcome-operator-readiness-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts
        self.ui = OperatorReadinessBlock.UI(
            title=title,
            rows_wrapper=rows_wrapper,
            rows=row_widgets,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.rows_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.ui.title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

    def _connect_signals(self) -> None:
        signals.ADB_SERVER.ADBServerStarted.connect(self._on_adb_server_started)
        signals.ADB_SERVER.ADBServerStopped.connect(self._on_adb_server_stopped)

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
        pass

    ### Slots ###

    @Slot()
    def _on_adb_server_started(self) -> None:
        """Update the readiness row when the ADB server starts."""
        self.ui.rows[self.ROWS_INDEX_MAPPING["host"]].update(
            label="Host",
            detail="ADB bridge standing by",
            status="READY",
            status_kind="ready",
        )

    @Slot()
    def _on_adb_server_stopped(self) -> None:
        """Update the readiness row when the ADB server stops."""
        self.ui.rows[self.ROWS_INDEX_MAPPING["host"]].update(
            label="Host",
            detail="ADB bridge stopped",
            status="ERROR",
            status_kind="error",
        )

    @Slot(str, str, str)
    def _on_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        """Update the readiness row when the device selection succeeds."""
        self.ui.rows[self.ROWS_INDEX_MAPPING["device"]].update(
            label="Device",
            detail=f"Device {device_name} linked",
            status="READY",
            status_kind="ready",
        )
        self.ui.rows[self.ROWS_INDEX_MAPPING["location"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["location"]]
        )
        self.ui.rows[self.ROWS_INDEX_MAPPING["simulation"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["simulation"]]
        )

    @Slot(str)
    def _on_remove_active_device_succeeded(self, device_id: str) -> None:
        """Update the readiness row when the active device is removed."""
        self.ui.rows[self.ROWS_INDEX_MAPPING["device"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["device"]]
        )
        self.ui.rows[self.ROWS_INDEX_MAPPING["location"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["location"]]
        )
        self.ui.rows[self.ROWS_INDEX_MAPPING["simulation"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["simulation"]]
        )

    @Slot(str, int, str, int, float, float, str)
    def _on_simulation_location_validated(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        lat: float,
        lon: float,
        label: str,
    ) -> None:
        """Update the readiness row when the simulation location is validated."""
        self.ui.rows[self.ROWS_INDEX_MAPPING["location"]].update(
            label="Location",
            detail=f"Set to {km} on {line_code}-{line_troncon}",
            status="READY",
            status_kind="ready",
        )
        self.ui.rows[self.ROWS_INDEX_MAPPING["simulation"]].update(
            *self.texts.default_rows[self.ROWS_INDEX_MAPPING["simulation"]]
        )


__all__ = ["OperatorReadinessBlock", "ReadinessRow"]
