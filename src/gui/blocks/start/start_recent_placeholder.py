"""Recent-session empty-state placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from gui.blocks.base import Block
from gui.blocks.start.start_settings import start_settings
from gui.colors import Theme, get_current_palette, get_current_theme, qcolor_from_css
from gui.icons import GenericIcons, icon_qt_path_for_theme
from gui.settings import Settings


class RecentSessionGlyph(QFrame):
    """Small session-file glyph with timeline points and star accents."""

    _SIZE = QSize(
        start_settings.RECENT_EMPTY_GLYPH_WIDTH,
        start_settings.RECENT_EMPTY_GLYPH_HEIGHT,
    )
    _FILE_ICON_PX = start_settings.RECENT_EMPTY_FILE_ICON_SIZE

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the painted recent-session glyph."""
        super().__init__(parent)
        self.setObjectName("start-recent-placeholder-glyph")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(self._SIZE)
        self._theme: Theme = get_current_theme()

    def sizeHint(self) -> QSize:
        """Return the fixed visual size used by the empty-state layout."""
        return self._SIZE

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the file icon color after a theme change."""
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the file, side timeline points, connector segments, and stars."""
        super().paintEvent(event)
        palette = get_current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center = self.rect().center()
        soft_color = qcolor_from_css(palette.PRIMARY_SOFT)
        border_color = qcolor_from_css(palette.PRIMARY_BORDER)
        primary_color = qcolor_from_css(palette.PRIMARY)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(soft_color)
        painter.drawRoundedRect(
            QRectF(center.x() - 27, center.y() - 29, 54, 58), 10, 10
        )

        line_pen = QPen(border_color, 2)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)
        painter.drawLine(QPointF(26, center.y()), QPointF(center.x() - 37, center.y()))
        painter.drawLine(QPointF(center.x() + 37, center.y()), QPointF(116, center.y()))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(primary_color)
        for x in (22, 120):
            painter.drawEllipse(QRectF(x - 4, center.y() - 4, 8, 8))

        icon = QIcon(icon_qt_path_for_theme(self._theme, GenericIcons.FILE))
        pixmap = icon.pixmap(QSize(self._FILE_ICON_PX, self._FILE_ICON_PX))
        painter.drawPixmap(
            center.x() - self._FILE_ICON_PX // 2,
            center.y() - self._FILE_ICON_PX // 2,
            pixmap,
        )

        painter.setBrush(primary_color)
        painter.setPen(Qt.PenStyle.NoPen)
        for point, radius in (
            (QPointF(47, 19), 5.0),
            (QPointF(95, 23), 4.0),
            (QPointF(101, 67), 3.5),
            (QPointF(42, 66), 3.0),
        ):
            self._draw_star(painter, point, radius)
        painter.end()

    @staticmethod
    def _draw_star(painter: QPainter, center: QPointF, radius: float) -> None:
        """Draw a compact four-point sparkle."""
        points = QPolygonF(
            [
                QPointF(center.x(), center.y() - radius),
                QPointF(center.x() + radius * 0.32, center.y() - radius * 0.32),
                QPointF(center.x() + radius, center.y()),
                QPointF(center.x() + radius * 0.32, center.y() + radius * 0.32),
                QPointF(center.x(), center.y() + radius),
                QPointF(center.x() - radius * 0.32, center.y() + radius * 0.32),
                QPointF(center.x() - radius, center.y()),
                QPointF(center.x() - radius * 0.32, center.y() - radius * 0.32),
            ]
        )
        painter.drawPolygon(points)


class StartRecentPlaceholder(QFrame, Block):
    """No-recent-session placeholder for the welcome recent-session card."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "No recent sessions"
        description: Final[str] = "Run a simulation and its log will appear here."

    @dataclass
    class UI:
        glyph: RecentSessionGlyph
        title_label: QLabel
        description_label: QLabel

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the recent-session empty placeholder."""
        super().__init__(parent)
        self.texts = StartRecentPlaceholder.Text()
        self.setObjectName("start-recent-placeholder")
        self.setProperty("start-recent-placeholder", True)

        glyph = RecentSessionGlyph(self)

        title_label = QLabel(self.texts.title, self)
        title_label.setObjectName("start-recent-placeholder-title")
        title_label.setWordWrap(True)

        description_label = QLabel(self.texts.description, self)
        description_label.setObjectName("start-recent-placeholder-description")
        description_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_PANEL)
        layout.setSpacing(Settings.SPACING.SM)
        layout.addStretch(1)
        layout.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self.ui = StartRecentPlaceholder.UI(
            glyph=glyph,
            title_label=title_label,
            description_label=description_label,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Let the placeholder fill the recent-session card width."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(start_settings.RECENT_EMPTY_PLACEHOLDER_MIN_HEIGHT)
        self.ui.glyph.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.title_label.setMaximumWidth(
            start_settings.RECENT_EMPTY_CONTENT_MAX_WIDTH
        )
        self.ui.description_label.setMaximumWidth(
            start_settings.RECENT_EMPTY_CONTENT_MAX_WIDTH
        )

    def _set_alignment(self) -> None:
        """Center empty-state content."""
        self.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        """No CTA or external signal is owned by this passive placeholder."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the file icon for the active theme."""
        self.ui.glyph.apply_theme_icons(theme)


__all__ = ["RecentSessionGlyph", "StartRecentPlaceholder"]
