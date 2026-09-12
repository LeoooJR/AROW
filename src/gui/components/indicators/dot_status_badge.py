"""Reusable status badge with a colored dot and text label."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from gui.components.base.component import Component
from gui.constants.colors import Theme
from gui.constants.settings import Settings

DotStatusKind = Literal["ready", "success", "muted", "warning", "error"]


class DotStatusBadge(QFrame, Component):
    """Rounded text badge with a small state-colored dot."""

    @dataclass(frozen=True)
    class Text:
        """Current badge label."""

        label: str = ""

    @dataclass
    class UI:
        """Child widgets that render the dot and label."""

        dot: QFrame
        label: QLabel

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        kind: DotStatusKind = "muted",
        object_name: str = "dot-status-badge",
        property_name: str = "dot-status-badge",
    ) -> None:
        """Create a reusable dot status badge.

        Args:
            parent: Optional Qt parent widget.
            text: Badge label.
            kind: Visual state consumed by the stylesheet.
            object_name: Object name consumed by the stylesheet.
            property_name: Dynamic property name consumed by the stylesheet.
        """
        super().__init__(parent)
        self.texts = DotStatusBadge.Text(label=text)
        self._kind: DotStatusKind = kind
        self._property_name = property_name

        self.setObjectName(object_name)
        self.setProperty(self._property_name, kind)

        dot = QFrame(self)
        dot.setObjectName("dot-status-badge-dot")
        dot.setProperty(self._property_name, kind)
        dot.setFixedSize(8, 8)

        label = QLabel(text, self)
        label.setObjectName("dot-status-badge-label")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(Settings.SPACING.XS)
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(layout)

        self.ui = DotStatusBadge.UI(dot=dot, label=label)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.ui.label.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme-dependent icons when the badge gains any."""
        pass

    def set_status(self, text: str, kind: DotStatusKind = "muted") -> None:
        """Update badge text and visual kind."""
        self.texts = DotStatusBadge.Text(label=text)
        self._kind = kind
        self.setProperty(self._property_name, kind)
        self.ui.dot.setProperty(self._property_name, kind)
        self.ui.label.setText(text)
        for widget in (self, self.ui.dot, self.ui.label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def kind(self) -> DotStatusKind:
        """Return the current status kind."""
        return self._kind
