"""Titled group box container component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from gui.colors import Theme
from gui.components.base.component import Component


class GroupBox(QGroupBox, Component):
    """
    Group box that displays a title and a content area.
    """

    @dataclass(frozen=True)
    class Text:
        """Group title string mirrored for dataclass symmetry."""

        title: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the group box."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        layout: QVBoxLayout | QHBoxLayout | None = None,
        widgets: list[QWidget] | None = None,
        title: str = "",
    ):
        """Create a titled group with optional pre-built layout and children.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            layout: Inner layout to attach before adding widgets.
            widgets: Optional child widgets appended to the inner layout.
            title: Group box title text.
        """
        super().__init__(parent, title=title, alignment=Qt.AlignmentFlag.AlignLeft)
        self.texts = GroupBox.Text(title=title)
        self.ui = GroupBox.UI()
        self.setProperty("group-box", True)
        self.setFlat(False)
        if layout is not None:
            self.setLayout(layout)
        if widgets is not None:
            for widget in widgets:
                self.layout().addWidget(widget)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
