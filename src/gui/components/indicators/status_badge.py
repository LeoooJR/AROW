"""Reusable textual status badge component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.components.base.component import Component
from gui.constants.colors import Theme

StatusBadgeKind = str  # "not-set" | "ready" | "muted" | "error"


class StatusBadge(QLabel, Component):
    """Small pill-like badge with a status-specific visual kind."""

    @dataclass(frozen=True)
    class Text:
        """Current badge label."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references."""

        pass

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        kind: StatusBadgeKind = "muted",
        object_name: str = "status-badge",
        property_name: str = "status-badge",
        size_policy: tuple[QSizePolicy.Policy, QSizePolicy.Policy] | None = None,
    ) -> None:
        """Create a status badge.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Initial badge text.
            kind: Dynamic style kind consumed by the stylesheet.
            object_name: Object name consumed by the stylesheet.
            property_name: Dynamic property name consumed by the stylesheet.
            size_policy: Optional explicit size policy.
        """
        super().__init__(text, parent)
        self.texts = StatusBadge.Text(label=text)
        self.ui = StatusBadge.UI()
        self._property_name = property_name
        self._size_policy = size_policy or (
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.setObjectName(object_name)
        self.setProperty(self._property_name, kind)
        self._kind: StatusBadgeKind = kind
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(*self._size_policy)

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme-dependent icons when the badge gains any."""
        pass

    def set_status(self, text: str, kind: StatusBadgeKind = "muted") -> None:
        """Update badge text and style kind."""
        self.setText(text)
        self.texts = StatusBadge.Text(label=text)
        self._kind = kind
        self.setProperty(self._property_name, kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def kind(self) -> StatusBadgeKind:
        """Return the current status style kind."""
        return self._kind
