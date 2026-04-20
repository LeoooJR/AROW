"""
Shared helpers for GUI animations.
"""

import math
from typing import Literal

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget

from gui.settings import Settings

Axis = Literal["horizontal", "vertical"]


def compute_sine_pulse_level(elapsed_ms: int, cycle_ms: int) -> int:
    """
    Convert elapsed time to a smooth intensity level in range [0..10].
    One sine period per cycle: 0 -> 1 -> 0.
    """
    t = (elapsed_ms % cycle_ms) / max(cycle_ms, 1)
    intensity = math.sin(math.pi * t)
    level = min(10, int(round(intensity * 10)))
    return max(0, level)


def apply_highlight_level(widget: QWidget, property_name: str, level: int) -> None:
    """Set a highlight level property and refresh style on the widget."""
    widget.setProperty(property_name, str(level))
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _animation_property_name(axis: Axis) -> bytes:
    """Map a logical axis to the corresponding QWidget size bound property."""
    return b"maximumHeight" if axis == "vertical" else b"maximumWidth"


def _measure_expanded_extent(widget: QWidget, axis: Axis) -> int:
    """Return the size hint extent for the requested axis after layout activation."""
    if widget.layout() is not None:
        widget.layout().activate()
    widget.updateGeometry()
    hint = widget.sizeHint()
    return hint.height() if axis == "vertical" else hint.width()


def _current_extent(widget: QWidget, axis: Axis) -> int:
    """Read the current rendered extent for the requested axis."""
    return widget.height() if axis == "vertical" else widget.width()


def animate_widget_visibility(
    widget: QWidget,
    *,
    visible: bool,
    axis: Axis,
    collapsed_size: int = 0,
    expanded_size: int | None = None,
    content_widget: QWidget | None = None,
    hide_widget_when_collapsed: bool = False,
) -> None:
    """Animate a widget between visible and collapsed states along one axis."""
    property_name = _animation_property_name(axis)
    animation_key = property_name.decode("ascii")
    active_animations = getattr(widget, "_visibility_animations", {})
    current_animation = active_animations.get(animation_key)

    if current_animation is not None:
        current_animation.stop()

    if visible:
        widget.setVisible(True)
        if content_widget is not None:
            content_widget.setVisible(True)

    if widget.parentWidget() and widget.parentWidget().layout() is not None:
        widget.parentWidget().layout().activate()

    start_value = max(collapsed_size, _current_extent(widget, axis))
    if start_value <= 0 and not visible:
        start_value = max(
            collapsed_size,
            (
                expanded_size
                if expanded_size is not None
                else _measure_expanded_extent(widget, axis)
            ),
        )

    if visible:
        end_value = max(
            collapsed_size,
            (
                expanded_size
                if expanded_size is not None
                else _measure_expanded_extent(widget, axis)
            ),
        )
    else:
        end_value = collapsed_size

    animation = QPropertyAnimation(widget, property_name, widget)
    animation.setDuration(Settings.ANIMATION.PANEL_VISIBILITY_DURATION)
    animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
    animation.setStartValue(start_value)
    animation.setEndValue(end_value)

    def _on_finished() -> None:
        if visible:
            if axis == "vertical":
                widget.setMaximumHeight(Settings.PANEL.UNBOUNDED_HEIGHT)
            else:
                widget.setMaximumWidth(Settings.PANEL.UNBOUNDED_HEIGHT)
        else:
            if content_widget is not None:
                content_widget.setVisible(False)
            if hide_widget_when_collapsed:
                widget.setVisible(False)

        widget.updateGeometry()
        stored_animations = getattr(widget, "_visibility_animations", {})
        if stored_animations.get(animation_key) is animation:
            stored_animations.pop(animation_key, None)

    animation.finished.connect(_on_finished)
    active_animations[animation_key] = animation
    setattr(widget, "_visibility_animations", active_animations)

    if axis == "vertical":
        widget.setMaximumHeight(start_value)
    else:
        widget.setMaximumWidth(start_value)
    widget.updateGeometry()
    animation.start()
