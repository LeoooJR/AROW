"""Map rendering placeholder state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
)
from PySide6.QtGui import QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.blocks.base import Block
from gui.colors import Theme, get_current_palette, get_current_theme, qcolor_from_css
from gui.icons import GenericIcons, icon_qt_path_for_theme
from gui.settings import Settings
from gui.wrapper import HorizontalLayoutWrapper


class MapLoadingGlyph(QFrame):
    """Map glyph with a dotted satellite-style orbit."""

    _SIZE = QSize(154, 126)
    _MAP_ICON_PX = 58

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the painted loading glyph."""
        super().__init__(parent)
        self.setObjectName("map-loading-glyph")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self._SIZE)
        self._theme: Theme = get_current_theme()

    def sizeHint(self) -> QSize:
        """Return the preferred visual size."""
        return self._SIZE

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the map icon for the active theme."""
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the loading glyph."""
        super().paintEvent(event)
        palette = get_current_palette()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()
        orbit_rect = QRectF(-56, -34, 112, 68)

        painter.save()
        painter.translate(center)
        painter.rotate(-14)

        orbit_pen = QPen(qcolor_from_css(palette.PRIMARY), 1.8)
        orbit_pen.setStyle(Qt.PenStyle.DashLine)
        orbit_pen.setDashPattern([4, 5])
        orbit_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(orbit_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(orbit_rect)

        angle = math.radians(24)
        dot_x = (orbit_rect.width() / 2) * math.cos(angle)
        dot_y = (orbit_rect.height() / 2) * math.sin(angle)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor_from_css(palette.PRIMARY))
        painter.drawEllipse(QRectF(dot_x - 5, dot_y - 5, 10, 10))
        painter.restore()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(qcolor_from_css(palette.PRIMARY_SOFT))
        painter.drawEllipse(QRectF(center.x() - 34, center.y() - 34, 68, 68))

        icon = QIcon(icon_qt_path_for_theme(self._theme, GenericIcons.MAP))
        pixmap = icon.pixmap(QSize(self._MAP_ICON_PX, self._MAP_ICON_PX))
        painter.drawPixmap(
            int(center.x() - self._MAP_ICON_PX / 2),
            int(center.y() - self._MAP_ICON_PX / 2),
            pixmap,
        )
        painter.end()


class MapLoadingPlaceholder(QFrame, Block):
    """Placeholder shown while the map workspace is being generated."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Preparing map"
        description: Final[str] = (
            "Building the map workspace for the selected device. This can take a moment."
        )
        descriptor: Final[str] = "Generating map..."

    @dataclass
    class UI:
        glyph: MapLoadingGlyph
        title_label: QLabel
        description_label: QLabel
        descriptor: QFrame
        descriptor_label: QLabel

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the map-loading placeholder."""
        super().__init__(parent)
        self.texts = MapLoadingPlaceholder.Text()
        self.setObjectName("map-loading-placeholder")
        self.setProperty("map-placeholder-state", True)

        glyph = MapLoadingGlyph(self)

        title_label = QLabel(self.texts.title, self)
        title_label.setObjectName("map-placeholder-title")
        title_label.setWordWrap(True)

        description_label = QLabel(self.texts.description, self)
        description_label.setObjectName("map-placeholder-description")
        description_label.setWordWrap(True)

        descriptor_label = QLabel(self.texts.descriptor, self)
        descriptor_label.setObjectName("map-loading-descriptor-label")

        descriptor = HorizontalLayoutWrapper(
            self,
            widgets=[descriptor_label],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        descriptor.setObjectName("map-loading-descriptor")
        descriptor.setProperty("passive-cta", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_PANEL)
        layout.setSpacing(Settings.SPACING.SM)
        layout.addStretch(1)
        layout.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addWidget(descriptor, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self.setLayout(layout)

        self.ui = MapLoadingPlaceholder.UI(
            glyph=glyph,
            title_label=title_label,
            description_label=description_label,
            descriptor=descriptor,
            descriptor_label=descriptor_label,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Preserve the expanding map placeholder behavior."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.glyph.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.descriptor.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        """Center loading placeholder content."""
        self.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.descriptor.get_layout().setAlignment(
            self.ui.descriptor_label, Qt.AlignmentFlag.AlignCenter
        )

    def _connect_signals(self) -> None:
        """No user action is available while loading."""
        pass

    def play_helper_animation(
        self,
        previous_animation: QSequentialAnimationGroup | None,
    ) -> QSequentialAnimationGroup:
        """Pulse the painted glyph to show the loading placeholder is alive."""
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
        """Refresh painted glyph icons for the active theme."""
        self.ui.glyph.apply_theme_icons(theme)
