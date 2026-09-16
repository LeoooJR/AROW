"""Raster image label component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from gui.components.base.component import Component
from gui.constants.colors import Theme


class Image(QLabel, Component):
    """
    Label that displays an image.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the image label."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the image label."""

        pass

    def __init__(self, parent: QWidget | None, image_path: str):
        """Load a pixmap from disk and enable scaled contents.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            image_path: Path to the raster image asset.
        """
        super().__init__(parent)
        self.texts = Image.Text()
        self.ui = Image.UI()
        self.setProperty("image", True)
        self.setPixmap(QPixmap(image_path))
        self.setScaledContents(True)
        self._finalize_ui_hooks()

    def set_pixmap_path(self, image_path: str) -> None:
        """Reload the pixmap from a (possibly theme-specific) Qt resource path."""
        self.setPixmap(QPixmap(image_path))

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme-dependent media when the image gains any."""
        pass
