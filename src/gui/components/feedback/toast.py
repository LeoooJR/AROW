"""Transient toast notification component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui.components.base.component import Component
from gui.components.feedback.feedback_settings import feedback_settings
from gui.components.media import get_svg_size
from gui.components.media.svg import SVG
from gui.constants.colors import Theme, get_current_theme, get_palette
from gui.constants.icons import GenericIcons, icon_qt_path
from gui.constants.settings import Settings


class Toast(QWidget, Component):
    """Transient top-level notification with severity styling."""

    @dataclass(frozen=True)
    class Text:
        """Toast body and severity level token."""

        message: str = ""
        level: str = "info"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the toast."""

        pass

    def __init__(
        self, parent: QWidget, message: str, level: str = "info", duration: int = 3000
    ):
        """Create a short-lived top-level toast (parent is ignored for window flags).

        Args:
            parent: Logical owner used only for context; toast is top-level.
            message: Body text shown in the banner.
            level: Visual style token such as info, success, warning, or error.
            duration: Auto-close delay in milliseconds.
        """
        # Ignore parent completely - create as completely independent top-level window
        # This prevents any layout interference with parent widgets
        super().__init__(None)
        self.texts = Toast.Text(message=message, level=level)
        self.ui = Toast.UI()

        # Set window flags BEFORE any other operations
        # Using Dialog flag for better cross-platform behavior
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Set attributes for better display
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        # Set main widget styling (transparent to show shadow)
        self.setObjectName("toast")
        theme = get_current_theme()
        palette = get_palette(theme)
        self.setStyleSheet(f"""
            QWidget#toast {{
                background-color: {palette.TRANSPARENT};
            }}
        """)

        # Create label with proper styling
        label = QLabel(message, self)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setWordWrap(True)

        # Create inner container for content (needed to combine shadow and opacity effects)
        inner_widget = QWidget(self)
        inner_widget.setObjectName("toast-inner")

        level_styles = {
            "info": (palette.INFO, GenericIcons.INFO),
            "success": (palette.SUCCESS, GenericIcons.CHECK),
            "warning": (palette.WARNING, GenericIcons.EXCLAMATION),
            "error": (palette.ERROR, GenericIcons.X_CIRCLE),
        }
        color, icon = level_styles.get(level, level_styles["info"])
        icon_path = icon_qt_path(icon)

        inner_widget.setStyleSheet(f"""
            QWidget#toast-inner {{
                background-color: {palette.SURFACE_ELEVATED};
                border: 1px solid {palette.BORDER_SUBTLE};
                border-left: 4px solid {color};
                border-radius: {Settings.BORDER_RADIUS.LG}px;
            }}
            QLabel {{
                color: {palette.TEXT_PRIMARY};
                background-color: {palette.TRANSPARENT};
                font-family: "{Settings.FONT.FAMILY}";
                font-size: {Settings.FONT.SIZE_DEFAULT}px;
                font-weight: {Settings.FONT.WEIGHT_NORMAL};
                padding: 0px;
                margin: 0px;
            }}
        """)

        inner_layout = QHBoxLayout(inner_widget)
        inner_layout.setContentsMargins(*feedback_settings.TOAST.MARGIN)
        inner_layout.setSpacing(Settings.SPACING.ICON_SPACING)

        svg = SVG(icon_path, inner_widget)
        svg.setFixedSize(get_svg_size(label.font().pointSize()))
        svg.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        inner_layout.addWidget(svg)
        inner_layout.addWidget(label, 1)

        # Set main widget layout to contain inner widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(inner_widget)

        # Set minimum and maximum size for better appearance
        self.setMinimumWidth(feedback_settings.TOAST.MIN_WIDTH)
        self.setMaximumWidth(feedback_settings.TOAST.MAX_WIDTH)
        self.adjustSize()

        # Position the window
        self._move_to_bottom_right()

        # Add shadow effect to main widget for modern appearance
        shadow_effect = QGraphicsDropShadowEffect(self)
        shadow_effect.setBlurRadius(feedback_settings.SHADOW.BLUR_RADIUS)
        shadow_effect.setXOffset(feedback_settings.SHADOW.X_OFFSET)
        shadow_effect.setYOffset(feedback_settings.SHADOW.Y_OFFSET)
        shadow_effect.setColor(
            QColor(*feedback_settings.SHADOW.COLOR_RGBA)
        )  # Subtle black shadow with transparency
        self.setGraphicsEffect(shadow_effect)

        # Add opacity effect to inner widget for fade animation
        self._opacity_effect = QGraphicsOpacityEffect(inner_widget)
        inner_widget.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        # Show the window
        self.show()
        self.raise_()

        # Fade in animation
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in.setDuration(feedback_settings.TOAST.FADE_IN_DURATION)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

        # Auto-close after duration (owned timer to stop safely on teardown)
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.close)
        self._auto_close_timer.start(duration)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme-dependent icons when the toast gains any."""
        pass

    def _move_to_bottom_right(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            offset = feedback_settings.TOAST.OFFSET
            x = geo.right() - self.width() - offset
            y = geo.bottom() - self.height() - offset
            self.move(x, y)

    def closeEvent(self, event) -> None:
        """Stop runtime resources before Qt destroys the toast hierarchy."""
        if hasattr(self, "_auto_close_timer") and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
        if (
            hasattr(self, "_fade_in")
            and self._fade_in.state() == QAbstractAnimation.State.Running
        ):
            self._fade_in.stop()
        super().closeEvent(event)
