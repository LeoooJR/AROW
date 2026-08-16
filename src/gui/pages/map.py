"""
This file contains all graphical elements related to the map panel.
"""

from dataclasses import dataclass

from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from gui.blocks.map import MapBlock
from gui.constants.colors import Theme
from gui.constants.settings import Settings


class MapPage(QFrame):
    """
    Panel that displays the map view.
    """

    @dataclass(frozen=True)
    class Text:
        """Panel title for the map tab."""

        pass

    @dataclass
    class UI:
        """Panel title and embedded map block."""

        map_block: MapBlock

    def __init__(self, parent=None):
        """Build the framed map panel with title and legend hook.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: MapPage.UI
        self.texts = MapPage.Text()

        self.setObjectName("map-panel")
        self.setProperty("main-panel", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(
            Settings.PANEL.SECTION_SPACING
        )  # Consistent spacing between major sections

        map_block = MapBlock(self)
        layout.addWidget(map_block, 1)
        map_block.setVisible(True)

        self.setLayout(layout)

        self.ui: MapPage.UI = MapPage.UI(map_block=map_block)

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the map panel."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        pass

    def _connect_signals(self) -> None:
        """Connect signals for the map panel and its UI widgets."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.map_block.apply_theme_icons(theme)

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.map_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
