"""Panel title row component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.components.media.svg import SVG
from gui.settings import Settings
from gui.svg import get_svg_size


class PanelTitle(QFrame, Component):
    """
    Widget that displays a panel title.
    """

    @dataclass(frozen=True)
    class Text:
        """Title string used for styling and dataclass symmetry."""

        title: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the title row."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        text="",
        font_size=24,
        font_weight=QFont.Weight.DemiBold,
        icon_path=None,
        icon_size=None,
    ):
        """Build a horizontal title with optional leading icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Title string.
            font_size: Point size for the title label.
            font_weight: Qt font weight for the title label.
            icon_path: Optional SVG path; omitted hides the icon.
            icon_size: Fixed icon size; derived from font when omitted.
        """
        super().__init__(parent)
        self.texts = PanelTitle.Text(title=text)
        self.ui = PanelTitle.UI()

        self.setProperty("panel-title", True)

        # Calculate icon size based on font size if not provided (icon should be ~1.3x font size for good visual balance)
        if icon_size is None:
            icon_size = get_svg_size(font_size)

        layout = QHBoxLayout()
        # Add padding for better visual spacing within panels
        layout.setContentsMargins(
            Settings.PANEL.TITLE_PADDING_LEFT,
            Settings.PANEL.TITLE_PADDING_TOP,
            Settings.PANEL.TITLE_PADDING_RIGHT,
            Settings.PANEL.TITLE_PADDING_BOTTOM,
        )
        layout.setSpacing(
            Settings.PANEL.TITLE_ICON_SPACING
        )  # Increased spacing for better visual separation

        self._leading_svg: SVG | None = None
        if icon_path is not None:
            self._leading_svg = SVG(icon_path, self)
            self._leading_svg.setFixedSize(icon_size)
            self._leading_svg.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
            )
            layout.addWidget(self._leading_svg)

        label = QLabel(text, self)
        label.setProperty("section-title", True)
        label.setFont(QFont(Settings.FONT.FAMILY, font_size, font_weight))
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label)

        self.setLayout(layout)
        self.setMaximumSize(layout.sizeHint())
        self._finalize_ui_hooks()

    def set_leading_icon_path(self, path: str) -> None:
        """Swap the title-leading SVG resource (e.g. after a light/dark theme change)."""
        if self._leading_svg is not None:
            self._leading_svg.set_path(path)

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass
