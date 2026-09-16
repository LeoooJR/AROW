"""Designed status and decision card for managed application shutdown."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from gui.components.base.component import Component
from gui.components.buttons.button import Button
from gui.components.containers.container_settings import container_settings
from gui.components.indicators.progress_bar import ProgressBar
from gui.components.labels.demi_bold_text import DemiBoldText
from gui.components.labels.helper_text import HelperText
from gui.components.media.svg import SVG
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons, icon_qt_path_for_theme
from gui.constants.settings import Settings


class ShutdownCardMode(Enum):
    """Visual states presented during managed shutdown."""

    CLOSING = "closing"
    DECISION = "decision"
    WAITING = "waiting"


class ShutdownCard(QFrame, Component):
    """Authentication-card-inspired shutdown status and decision surface."""

    WaitRequested = Signal()
    ForceCloseRequested = Signal()

    @dataclass(frozen=True)
    class Text:
        closing_title: Final[str] = "Closing AROW"
        closing_description: Final[str] = "Finishing background work safely…"
        decision_title: Final[str] = "Shutdown is taking longer"
        waiting_title: Final[str] = "Still waiting…"
        waiting_description: Final[str] = (
            "AROW will close automatically when the remaining work finishes."
        )
        caution: Final[str] = "Force close can leave the current operation incomplete."
        wait_action: Final[str] = "Keep waiting"
        force_action: Final[str] = "Force close"

    @dataclass
    class UI:
        status_halo: QFrame
        status_icon: SVG
        title: DemiBoldText
        description: HelperText
        progress: ProgressBar
        caution: HelperText
        wait_button: Button
        force_button: Button

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the managed-shutdown status and decision card.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = ShutdownCard.Text()
        self._mode = ShutdownCardMode.CLOSING
        self.setObjectName("card")
        self.setProperty("shutdown-card", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Application shutdown")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.SM)

        status_halo = QFrame(self)
        status_halo.setProperty("shutdown-status-halo", True)
        status_halo.setFixedSize(
            container_settings.SHUTDOWN_CARD.STATUS_ICON_SIZE,
            container_settings.SHUTDOWN_CARD.STATUS_ICON_SIZE,
        )
        halo_layout = QHBoxLayout(status_halo)
        halo_layout.setContentsMargins(0, 0, 0, 0)
        status_icon = SVG("", status_halo)
        status_icon.setFixedSize(
            container_settings.SHUTDOWN_CARD.STATUS_GLYPH_SIZE,
            container_settings.SHUTDOWN_CARD.STATUS_GLYPH_SIZE,
        )
        halo_layout.addWidget(status_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_halo, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = DemiBoldText(self, self.texts.closing_title)
        description = HelperText(self, self.texts.closing_description)
        description.setWordWrap(True)
        description.setMinimumHeight(40)
        progress = ProgressBar(self, minimum=0, maximum=0, text_visible=False)
        caution = HelperText(self, self.texts.caution)
        caution.setProperty("shutdown-caution", True)
        caution.setWordWrap(True)
        caution.setMinimumHeight(44)
        wait_button = Button(self, self.texts.wait_action)
        force_button = Button(self, self.texts.force_action)
        force_button.setProperty("destructive-action", True)
        force_button.setAccessibleDescription(
            "Close AROW even if background work has not finished."
        )

        for widget in (
            title,
            description,
            progress,
            caution,
            wait_button,
            force_button,
        ):
            layout.addWidget(widget)

        self.ui = ShutdownCard.UI(
            status_halo=status_halo,
            status_icon=status_icon,
            title=title,
            description=description,
            progress=progress,
            caution=caution,
            wait_button=wait_button,
            force_button=force_button,
        )
        self._finalize_ui_hooks()
        self.show_closing()

    @property
    def mode(self) -> ShutdownCardMode:
        """Return the shutdown state currently presented by the card."""
        return self._mode

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(container_settings.SHUTDOWN_CARD.MIN_WIDTH)
        self.setMaximumWidth(container_settings.SHUTDOWN_CARD.MAX_WIDTH)

    def _set_alignment(self) -> None:
        self.ui.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.caution.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        self.ui.wait_button.clicked.connect(self.WaitRequested)
        self.ui.force_button.clicked.connect(self.ForceCloseRequested)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh the shutdown status icon for the active theme."""
        self.ui.status_icon.set_path(
            icon_qt_path_for_theme(theme, GenericIcons.EXCLAMATION)
        )

    def show_closing(self) -> None:
        """Present the initial non-interactive shutdown progress state."""
        self._set_mode(
            ShutdownCardMode.CLOSING,
            title=self.texts.closing_title,
            description=self.texts.closing_description,
        )

    def show_decision(self, description: str) -> None:
        """Present timeout context and the wait/force choice."""
        self._set_mode(
            ShutdownCardMode.DECISION,
            title=self.texts.decision_title,
            description=description,
        )
        self.ui.wait_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_waiting(self) -> None:
        """Present continued progress while retaining the force-close escape."""
        self._set_mode(
            ShutdownCardMode.WAITING,
            title=self.texts.waiting_title,
            description=self.texts.waiting_description,
        )
        self.ui.force_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _set_mode(
        self, mode: ShutdownCardMode, *, title: str, description: str
    ) -> None:
        self._mode = mode
        self.setProperty("shutdown-mode", mode.value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.ui.title.setText(title)
        self.ui.description.setText(description)
        decision = mode is ShutdownCardMode.DECISION
        self.ui.caution.setVisible(mode is not ShutdownCardMode.CLOSING)
        self.ui.wait_button.setVisible(decision)
        self.ui.force_button.setVisible(mode is not ShutdownCardMode.CLOSING)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Treat Escape as the safe wait choice only when a decision is open."""
        if event.key() == Qt.Key.Key_Escape and self._mode is ShutdownCardMode.DECISION:
            self.WaitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
