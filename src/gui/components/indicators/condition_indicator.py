"""Circular condition state indicator component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QWidget

from gui.colors import Theme, get_current_palette
from gui.components.base.component import Component
from gui.components.indicators.indicator_settings import indicator_settings
from gui.settings import Settings

IndicatorState = str  # "default" | "valid" | "warning" | "error"


class ConditionIndicator(QFrame, Component):
    """
    Small top-right indicator with four states: default (grey), valid (green), warning (orange), error (red).
    Used to show if a condition is met before simulation (e.g. host identity). Visible but soft.
    Pulses (opacity animation) when state is warning or error to catch the user's eye.
    The circle is drawn in paintEvent so it stays round at any size (stylesheet border-radius fails on small widgets).
    Use objectName e.g. "host-identity-indicator" or "condition-indicator"; property "indicator-state" for stylesheet.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the indicator."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the indicator."""

        pass

    def __init__(
        self, parent: QWidget | None = None, object_name: str = "condition-indicator"
    ):
        """Create a small circular state indicator.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            object_name: Qt object name used for stylesheet targeting.
        """
        super().__init__(parent)
        self.texts = ConditionIndicator.Text()
        self.ui = ConditionIndicator.UI()
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        size = indicator_settings.CONDITION_INDICATOR_SIZE
        self.setFixedSize(size, size)
        self._state: IndicatorState = "default"
        self.set_state(self._state)
        self.setProperty("indicator-state", self._state)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._pulse_group: QSequentialAnimationGroup | None = None
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _indicator_color(self) -> str:
        """Return palette color for current state (for paintEvent)."""
        palette = get_current_palette()
        if self._state == "valid":
            return palette.SUCCESS
        if self._state == "warning":
            return palette.PRIMARY
        if self._state == "error":
            return palette.ERROR
        return palette.HELPER_TEXT  # default

    def paintEvent(self, event):
        """Draw a circle so the indicator stays round at any size (avoids stylesheet border-radius issues)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setBrush(QColor(self._indicator_color()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())
        painter.end()

    def set_state(self, state: IndicatorState) -> None:
        """Set indicator state: 'default' (grey), 'valid' (green), 'warning' (orange), 'error' (red)."""
        if state == self._state:
            return
        self._state = state
        self.setProperty("indicator-state", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        if state in ("warning", "error"):
            self._start_pulse()
        else:
            self._stop_pulse()
            self._opacity_effect.setOpacity(1.0)

    def _start_pulse(self) -> None:
        half = indicator_settings.PULSE_DURATION // 2
        easing = QEasingCurve.Type.InOutSine
        out = QPropertyAnimation(self._opacity_effect, b"opacity")
        out.setDuration(half)
        out.setStartValue(1.0)
        out.setEndValue(0.45)
        out.setEasingCurve(easing)
        inc = QPropertyAnimation(self._opacity_effect, b"opacity")
        inc.setDuration(half)
        inc.setStartValue(0.45)
        inc.setEndValue(1.0)
        inc.setEasingCurve(easing)
        if (
            self._pulse_group is not None
            and self._pulse_group.state() == QAbstractAnimation.State.Running
        ):
            self._pulse_group.stop()
        self._pulse_group = QSequentialAnimationGroup(self)
        self._pulse_group.addAnimation(out)
        self._pulse_group.addAnimation(inc)
        self._pulse_group.finished.connect(self._on_pulse_finished)
        self._pulse_group.start()

    def _stop_pulse(self) -> None:
        if self._pulse_group is not None:
            self._pulse_group.finished.disconnect(self._on_pulse_finished)
            if self._pulse_group.state() == QAbstractAnimation.State.Running:
                self._pulse_group.stop()
            self._pulse_group = None

    def _on_pulse_finished(self) -> None:
        if self._state in ("warning", "error") and self._pulse_group is not None:
            self._pulse_group.start()

    def state(self) -> IndicatorState:
        return self._state
