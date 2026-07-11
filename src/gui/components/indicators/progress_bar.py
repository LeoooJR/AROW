"""Reusable progress bar component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QProgressBar, QSizePolicy, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.components.indicators.indicator_settings import indicator_settings


class ProgressBar(QProgressBar, Component):
    """
    Reusable progress bar with optional labels for integer values.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the progress bar."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the progress bar."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        minimum: int = 0,
        maximum: int = 100,
        value: int = 0,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        step_labels: list[str] | None = None,
        text_visible: bool = True,
    ):
        """Create a configurable progress indicator.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            minimum: Lowest progress value.
            maximum: Highest progress value.
            value: Initial progress value.
            orientation: Progress bar orientation.
            step_labels: Optional labels per integer value.
            text_visible: Whether progress text should be visible.
        """
        super().__init__(parent)
        self.texts = ProgressBar.Text()
        self.ui = ProgressBar.UI()
        self.setProperty("progress-bar", True)
        self.setFixedHeight(indicator_settings.PROGRESSBAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setInvertedAppearance(False)
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setOrientation(orientation)
        self.setValue(value)
        self.setTextVisible(text_visible)
        self._step_labels: list[str] = list(step_labels) if step_labels else []
        self._update_format(self.value())
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        self.valueChanged.connect(self._update_format)

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    @Slot(int)
    def _update_format(self, value: int) -> None:
        if 0 <= value < len(self._step_labels):
            self.setFormat(f"{value}. {self._step_labels[value]}")
        else:
            self.setFormat("%v")
