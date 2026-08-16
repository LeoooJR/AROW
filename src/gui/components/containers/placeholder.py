"""Empty-state placeholder component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.components.base.component import Component
from gui.components.containers.container_settings import container_settings
from gui.components.media.svg import SVG
from gui.constants.colors import Theme
from gui.constants.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.constants.settings import Settings


class PlaceHolder(QFrame, Component):
    """
    Empty-state placeholder: optional SVG on top, then centered text.
    Text uses a softer color (PLACEHOLDER_TEXT). Use icon_path to show an icon above the label.
    """

    _icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None

    @dataclass(frozen=True)
    class Text:
        """Optional plain-text snapshot when the body is a string."""

        text: str | None = None

    @dataclass
    class UI:
        """Primary text label and optional top icon."""

        text: QLabel
        svg: SVG

    def __init__(
        self,
        parent: QWidget | None,
        text: QLabel | str,
        minimum_width: int = 180,
        minimum_height: int = 150,
        stretch_widgets: bool = False,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
    ):
        """Build a vertically centered empty-state block.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Centered message as string or external label widget.
            minimum_width: Minimum width before default placeholder sizing applies.
            minimum_height: Minimum height before default placeholder sizing applies.
            stretch_widgets: Layout stretch factor for the text row when True.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown above the text.
        """
        super().__init__(parent)
        self.texts = PlaceHolder.Text(text=text if isinstance(text, str) else None)
        self.ui: PlaceHolder.UI
        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon

        self.setProperty("place-holder", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            container_settings.PLACEHOLDER.PADDING,
            container_settings.PLACEHOLDER.PADDING,
            container_settings.PLACEHOLDER.PADDING,
            container_settings.PLACEHOLDER.PADDING,
        )
        layout.setSpacing(container_settings.PLACEHOLDER.SPACING)

        self.setMinimumWidth(
            minimum_width
            if minimum_width != 180
            else container_settings.PLACEHOLDER.MIN_WIDTH
        )
        self.setMinimumHeight(
            minimum_height
            if minimum_height != 150
            else container_settings.PLACEHOLDER.MIN_HEIGHT
        )

        layout.addStretch()

        svg = SVG("", self)
        svg.hide()
        if icon is not None:
            icon_size = container_settings.PLACEHOLDER.ICON_SIZE
            svg.set_path(icon_qt_path(icon))
            svg.setFixedSize(icon_size, icon_size)
            svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            svg.show()
            layout.addWidget(svg)

        if isinstance(text, str):
            label = QLabel(text, self)
        else:
            label = text

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label, int(stretch_widgets))

        layout.addStretch()
        self.setLayout(layout)

        self.ui = PlaceHolder.UI(text=label, svg=svg)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        self.layout().setAlignment(self.ui.text, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(self.ui.svg, Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        if self._icon is not None:
            self.ui.svg.set_path(icon_qt_path_for_theme(theme, self._icon))

    def set_text(self, text: str) -> None:
        """Update the placeholder message.

        Args:
            text: New body string for the label.
        """
        self.ui.text.setText(text)

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None
    ) -> None:
        """Swap the illustration above the text.

        Args:
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown above the text.
        """
        if icon is None:
            return

        self._icon = icon
        self.ui.svg.set_path(icon_qt_path(self._icon))
