"""Step-based progress bar component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressBar, QSizePolicy, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.settings import Settings


class ProgressBar(QProgressBar, Component):
    """
    Step-based progress bar for pre-simulation steps.
    """

    DEFAULT_STEP_LABELS: list[str] = [
        "Not started",
        "Device selected",
        "Location set",
        "Ready to start",
    ]

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the progress bar."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the progress bar."""

        pass

    def __init__(self, parent: QWidget | None, step_labels: list[str] | None = None):
        """Create a four-step horizontal progress indicator.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            step_labels: Custom labels per step index; defaults to built-in list.
        """
        super().__init__(parent)
        self.texts = ProgressBar.Text()
        self.ui = ProgressBar.UI()
        self.setProperty("progress-bar", True)
        self.setFixedHeight(Settings.DIMENSION.PROGRESSBAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setInvertedAppearance(False)
        self.setMaximum(3)
        self.setMinimum(0)
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setValue(0)
        self.setTextVisible(True)
        self._step_labels: list[str] = (
            step_labels
            if step_labels is not None
            else list(ProgressBar.DEFAULT_STEP_LABELS)
        )
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

    def _update_format(self, value: int) -> None:
        if 0 <= value < len(self._step_labels):
            self.setFormat(f"{value}. {self._step_labels[value]}")
        else:
            self.setFormat("%v. Step %v")
