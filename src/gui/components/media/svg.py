"""SVG rendering label component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.settings import Settings


def get_svg_size(font_size: int) -> QSize:
    """Return a square SVG size scaled from the given font size."""
    if font_size < 20:
        multiplier = Settings.SVG.MULTIPLIER_SMALL
    else:
        multiplier = Settings.SVG.MULTIPLIER_LARGE
    size = int(multiplier * font_size)
    return QSize(size, size)


class SVG(QLabel, Component):
    """Custom QLabel that renders SVG using QSvgRenderer"""

    path: str

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the SVG label."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the SVG label."""

        pass

    def __init__(self, svg_path: str, parent: QWidget | None = None):
        """Load an SVG from disk and paint it in ``paintEvent``.

        Args:
            svg_path: Filesystem path to the SVG asset.
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = SVG.Text()
        self.setProperty("svg", True)
        self.path = svg_path
        self.renderer: QSvgRenderer | None = None
        self.set_path(svg_path)

        self.ui = SVG.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.renderer is not None:
            try:
                self.renderer.render(painter)
            except Exception as e:
                print(f"Error rendering SVG using QSvgRenderer: {e}")
        painter.end()

    def set_path(self, path: str):
        """Replace the SVG source and refresh rendering.

        Args:
            path: New filesystem path to an SVG asset.
        """
        self.path = path
        try:
            self.renderer = QSvgRenderer(self.path)
        except Exception as e:
            print(f"Error creating SVG renderer: {e}")
            self.renderer = None
        self.update()
