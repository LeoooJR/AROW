"""Empty-state CTA for the device selection list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QLabel,
    QFrame,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from gui.blocks.base import Block
from gui.colors import Theme, get_current_palette
from gui.components import Button, DotStatusBadge
from gui.icons import GenericIcons, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import VerticalLayoutWrapper


class DeviceDiscoveryGlyph(QFrame):
    """Small phone mark with restrained discovery rings."""

    _SIZE = QSize(112, 94)
    _PHONE_ICON_PX = 34

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the painted device discovery glyph."""
        super().__init__(parent)
        self.setObjectName("device-empty-state-glyph")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self._SIZE)
        self._theme: Theme = "light"

    def sizeHint(self) -> QSize:
        """Return the fixed visual size used by the empty-state layout."""
        return self._SIZE

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the phone icon color after a theme change."""
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        """Paint soft discovery rings plus the project phone icon."""
        super().paintEvent(event)
        palette = get_current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()
        ring_color = palette.PRIMARY_BORDER
        ring_pen = QPen(QColor(ring_color), 1.8)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for diameter in (58, 82):
            top_left_x = center.x() - diameter / 2
            top_left_y = center.y() - diameter / 2
            painter.drawEllipse(QRectF(top_left_x, top_left_y, diameter, diameter))

        painter.setPen(Qt.PenStyle.NoPen)
        pulse_fill = palette.PRIMARY_SOFT if self._theme == "light" else palette.SURFACE_ELEVATED
        painter.setBrush(QColor(pulse_fill))
        painter.drawEllipse(QRectF(center.x() - 25, center.y() - 25, 50, 50))

        icon = QIcon(icon_qt_path_for_theme(self._theme, GenericIcons.DEVICE))
        pixmap = icon.pixmap(QSize(self._PHONE_ICON_PX, self._PHONE_ICON_PX))
        painter.drawPixmap(
            center.x() - self._PHONE_ICON_PX // 2,
            center.y() - self._PHONE_ICON_PX // 2,
            pixmap,
        )
        painter.end()


class DeviceEmptyState(QFrame, Block):
    """CTA-first empty state for the available-device list."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "No device linked"
        description: Final[str] = "Connect an Android device to begin"
        status: Final[str] = "ADB ready"
        add_button: Final[str] = "Add device"
        refresh_button: Final[str] = "Scan again"

    @dataclass
    class UI:
        glyph: DeviceDiscoveryGlyph
        glyph_host: VerticalLayoutWrapper
        glyph_title_spacer: QSpacerItem
        title_label: QLabel
        description_label: QLabel
        status_badge: DotStatusBadge
        add_button: Button
        refresh_button: Button
        actions: VerticalLayoutWrapper

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the empty device CTA card."""
        super().__init__(parent)
        self.texts = DeviceEmptyState.Text()

        glyph = DeviceDiscoveryGlyph(self)
        glyph_host = VerticalLayoutWrapper(
            self,
            widgets=[glyph],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        glyph_host.setObjectName("device-empty-state-glyph-host")
        glyph_host.get_layout().setAlignment(glyph, Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(self.texts.title, self)
        title_label.setObjectName("device-empty-state-title")
        title_label.setWordWrap(True)

        description_label = QLabel(self.texts.description, self)
        description_label.setObjectName("device-empty-state-description")
        description_label.setWordWrap(True)

        status_badge = DotStatusBadge(self, text=self.texts.status, kind="ready")

        add_button = Button(self, self.texts.add_button, icon=GenericIcons.PLUS)
        add_button.setObjectName("device-empty-state-add-button")

        refresh_button = Button(
            self,
            self.texts.refresh_button,
            icon=GenericIcons.ARROW_CLOCKWISE,
        )
        refresh_button.setObjectName("device-empty-state-refresh-button")
        refresh_button.setProperty("secondary-button", True)

        actions = VerticalLayoutWrapper(
            self,
            widgets=[add_button, refresh_button],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        actions.setObjectName("device-empty-state-actions")

        glyph_title_spacer = QSpacerItem(
            1,
            Settings.LIST.DEVICE_EMPTY_STATE_GLYPH_TITLE_SPACING,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(
            *Settings.SPACING.MARGIN_PANEL
        )
        layout.setSpacing(Settings.SPACING.SM)
        layout.addStretch(1)
        layout.addWidget(glyph_host, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addItem(glyph_title_spacer)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addWidget(actions)
        layout.addWidget(status_badge, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self.setLayout(layout)

        self.ui = DeviceEmptyState.UI(
            glyph=glyph,
            glyph_host=glyph_host,
            glyph_title_spacer=glyph_title_spacer,
            title_label=title_label,
            description_label=description_label,
            status_badge=status_badge,
            add_button=add_button,
            refresh_button=refresh_button,
            actions=actions,
        )

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Let the CTA fill the available list viewport."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.glyph_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.actions.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.ui.add_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.refresh_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.status_badge.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )

    def fit_to_available_width(self, available_width: int) -> None:
        """Clamp preferred CTA widths to the actual list viewport."""
        card_width = max(
            0, min(Settings.LIST.DEVICE_EMPTY_STATE_WIDTH, available_width)
        )
        action_width = min(
            Settings.LIST.DEVICE_EMPTY_STATE_ACTION_WIDTH,
            max(0, card_width - (Settings.SPACING.LG * 2)),
        )
        self.setFixedWidth(card_width)
        self.ui.actions.setFixedWidth(action_width)
        self.ui.add_button.setFixedWidth(action_width)
        self.ui.refresh_button.setFixedWidth(action_width)

    def _set_alignment(self) -> None:
        """Center CTA content within the empty list viewport."""
        self.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.actions.get_layout().setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        """Emit the same view-level actions as the device-list toolbar."""
        self.ui.add_button.clicked.connect(view_signals.AddDeviceRequested.emit)
        self.ui.refresh_button.clicked.connect(
            view_signals.RefreshDeviceListRequested.emit
        )

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh all icon-bearing children for the active theme."""
        self.ui.glyph.apply_theme_icons(theme)
        self.ui.refresh_button.apply_theme_icons(theme)