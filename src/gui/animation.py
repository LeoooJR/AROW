"""
Shared helpers for GUI animations.
"""

import math

from PySide6.QtWidgets import QWidget


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
