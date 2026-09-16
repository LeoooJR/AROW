"""Managed-shutdown overlay displayed above the application shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from gui.components import ShutdownCard
from gui.constants.colors import Theme


class ShutdownOverlay(QWidget):
    """Block shell interaction while presenting managed-shutdown progress."""

    WaitRequested = Signal()
    ForceCloseRequested = Signal()

    @dataclass(frozen=True)
    class Text:
        background_work_delayed: Final[str] = (
            "Background work has not stopped yet. You can keep waiting or force "
            "AROW to close."
        )
        adb_close_delayed: Final[str] = (
            "The Android connection is still closing. You can keep waiting or "
            "force AROW to close."
        )

    @dataclass
    class UI:
        shutdown_card: ShutdownCard

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the modal managed-shutdown overlay.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = ShutdownOverlay.Text()
        self.setObjectName("shutdown-overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        card = ShutdownCard(self)
        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self.ui = ShutdownOverlay.UI(shutdown_card=card)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        card.WaitRequested.connect(self.WaitRequested)
        card.ForceCloseRequested.connect(self.ForceCloseRequested)

    def show_closing(self) -> None:
        """Show the initial progress-only shutdown state."""
        self.ui.shutdown_card.show_closing()
        self._present()

    def show_background_work_decision(self) -> None:
        """Offer choices for delayed pre-close background work."""
        self.ui.shutdown_card.show_decision(self.texts.background_work_delayed)
        self._present()

    def show_adb_close_decision(self) -> None:
        """Offer choices for delayed Android bridge teardown."""
        self.ui.shutdown_card.show_decision(self.texts.adb_close_delayed)
        self._present()

    def show_waiting(self) -> None:
        """Keep showing progress with force close still available."""
        self.ui.shutdown_card.show_waiting()
        self._present()

    def _present(self) -> None:
        self.raise_()
        self.show()
        self.ui.shutdown_card.setFocus(Qt.FocusReason.OtherFocusReason)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh shutdown card icons for the active theme."""
        self.ui.shutdown_card.apply_theme_icons(theme)
