"""No-device map placeholder state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    QSequentialAnimationGroup,
    Qt,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.blocks.base import Block
from gui.colors import Theme, get_current_palette
from gui.components.media import get_svg_size
from gui.icons import GenericIcons, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class DeviceRequiredMapGlyph(QFrame):
    """Device glyph with a dotted selection frame and direction cue."""

    _SIZE = QSize(180, 126)
    _PHONE_ICON_PX = 42

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the painted glyph."""
        super().__init__(parent)
        self.setObjectName("map-device-required-glyph")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self._SIZE)
        self._theme: Theme = "light"

    def sizeHint(self) -> QSize:
        """Return the preferred visual size."""
        return self._SIZE

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the device icon for the active theme."""
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the state glyph."""
        super().paintEvent(event)
        palette = get_current_palette()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        frame_rect = QRectF(18, 22, 76, 82)
        frame_pen = QPen(QColor(palette.PRIMARY_BORDER), 1.4)
        frame_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(frame_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame_rect, 12, 12)

        icon_center = frame_rect.center()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.PRIMARY_SOFT))
        painter.drawRoundedRect(
            QRectF(icon_center.x() - 26, icon_center.y() - 32, 52, 64), 10, 10
        )

        icon = QIcon(icon_qt_path_for_theme(self._theme, GenericIcons.DEVICE))
        pixmap = icon.pixmap(QSize(self._PHONE_ICON_PX, self._PHONE_ICON_PX))
        painter.drawPixmap(
            int(icon_center.x() - self._PHONE_ICON_PX / 2),
            int(icon_center.y() - self._PHONE_ICON_PX / 2),
            pixmap,
        )

        path = QPainterPath()
        path.moveTo(102, 70)
        path.cubicTo(122, 72, 116, 45, 140, 46)
        path.lineTo(154, 46)

        arrow_pen = QPen(QColor(palette.PRIMARY), 2)
        arrow_pen.setStyle(Qt.PenStyle.DashLine)
        arrow_pen.setDashPattern([4, 4])
        arrow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arrow_pen)
        painter.drawPath(path)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(palette.PRIMARY), 2))
        painter.drawLine(154, 46, 143, 35)
        painter.drawLine(154, 46, 143, 57)
        painter.end()


class DeviceRequiredMapPlaceholder(QFrame, Block):
    """CTA-first placeholder shown before a device is selected."""

    _CONTENT_MIN_WIDTH = 360
    _CONTENT_MAX_WIDTH = 420

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Choose a device to open the map"
        description: Final[str] = (
            "The map becomes available after an Android device is linked and selected."
        )
        cta: Final[str] = "Open device list"

    @dataclass
    class UI:
        glyph: DeviceRequiredMapGlyph
        title_label: QLabel
        description_label: QLabel
        open_device_list_button: QPushButton
        content: VerticalLayoutWrapper
        body: HorizontalLayoutWrapper

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the no-device map placeholder."""
        super().__init__(parent)
        self.texts = DeviceRequiredMapPlaceholder.Text()
        self.setObjectName("map-device-required-placeholder")
        self.setProperty("map-placeholder-state", True)

        glyph = DeviceRequiredMapGlyph(self)

        title_label = QLabel(self.texts.title, self)
        title_label.setObjectName("map-placeholder-title")
        title_label.setWordWrap(True)

        description_label = QLabel(self.texts.description, self)
        description_label.setObjectName("map-placeholder-description")
        description_label.setWordWrap(True)

        open_device_list_button = QPushButton(f" {self.texts.cta}", self)
        open_device_list_button.setObjectName("map-placeholder-open-device-list")
        open_device_list_button.setIcon(
            QIcon(icon_qt_path_for_theme("light", GenericIcons.LIST_UL))
        )
        open_device_list_button.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))

        content = VerticalLayoutWrapper(
            self,
            widgets=[title_label, description_label, open_device_list_button],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        content.setObjectName("map-device-required-content")

        body = HorizontalLayoutWrapper(
            self,
            widgets=[glyph, content],
            spacing=Settings.SPACING.LG,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        body.setObjectName("map-device-required-body")

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_PANEL)
        layout.setSpacing(Settings.SPACING.NONE)
        layout.addStretch(1)
        layout.addWidget(body)
        layout.addStretch(1)
        self.setLayout(layout)

        self.ui = DeviceRequiredMapPlaceholder.UI(
            glyph=glyph,
            title_label=title_label,
            description_label=description_label,
            open_device_list_button=open_device_list_button,
            content=content,
            body=body,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Preserve the expanding map placeholder behavior."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.glyph.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.content.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        self.ui.content.setMinimumWidth(self._CONTENT_MIN_WIDTH)
        self.ui.content.setMaximumWidth(self._CONTENT_MAX_WIDTH)
        self.ui.open_device_list_button.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        """Align no-device placeholder content."""
        self.layout().setAlignment(self.ui.body, Qt.AlignmentFlag.AlignCenter)
        self.ui.body.get_layout().setAlignment(self.ui.glyph, Qt.AlignmentFlag.AlignCenter)
        self.ui.body.get_layout().setAlignment(
            self.ui.content, Qt.AlignmentFlag.AlignVCenter
        )
        self.ui.content.get_layout().setAlignment(
            self.ui.open_device_list_button, Qt.AlignmentFlag.AlignLeft
        )

    def _connect_signals(self) -> None:
        """Connect the CTA to the left-panel visibility request."""
        self.ui.open_device_list_button.clicked.connect(
            lambda: view_signals.LeftPanelsVisibilityRequested.emit(True)
        )

    def play_helper_animation(
        self,
        previous_animation: QSequentialAnimationGroup | None,
    ) -> QSequentialAnimationGroup:
        """Pulse the painted glyph to draw attention to this placeholder."""
        if (
            previous_animation is not None
            and previous_animation.state() == QAbstractAnimation.State.Running
        ):
            previous_animation.stop()

        effect = self.ui.glyph.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(self.ui.glyph)
            self.ui.glyph.setGraphicsEffect(effect)

        half = Settings.ANIMATION.PLACEHOLDER_HELPER_DURATION // 2
        easing = QEasingCurve.Type.OutCubic

        anim_fade_out = QPropertyAnimation(effect, b"opacity")
        anim_fade_out.setDuration(half)
        anim_fade_out.setStartValue(1.0)
        anim_fade_out.setEndValue(0.55)
        anim_fade_out.setEasingCurve(easing)

        anim_fade_in = QPropertyAnimation(effect, b"opacity")
        anim_fade_in.setDuration(half)
        anim_fade_in.setStartValue(0.55)
        anim_fade_in.setEndValue(1.0)
        anim_fade_in.setEasingCurve(easing)

        animation = QSequentialAnimationGroup(self)
        animation.addAnimation(anim_fade_out)
        animation.addAnimation(anim_fade_in)
        animation.setLoopCount(Settings.ANIMATION.PLACEHOLDER_HELPER_ITERATION)
        animation.start()
        return animation

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh painted glyph icons while keeping the CTA icon black."""
        self.ui.glyph.apply_theme_icons(theme)
