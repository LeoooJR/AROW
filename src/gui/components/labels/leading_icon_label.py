"""Leading icon and label row component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.components.media.svg import SVG
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.svg import get_svg_size


class LeadingIconLabel(QWidget, Component):
    """
    Widget that displays a leading icon and a label.
    """

    @dataclass(frozen=True)
    class Text:
        """Optional plain-text snapshot when the text is a string."""

        text: str | None = None

    @dataclass
    class UI:
        """Widgets composing the leading icon label."""

        svg: SVG
        text: QLabel

    def __init__(
        self,
        parent: QWidget | None,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
        text: str | QLabel,
        font_weight: QFont.Weight = QFont.Weight.Normal,
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
    ):
        """Lay out a leading SVG icon beside a string or external ``QLabel``.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons.
            text: Caption string or pre-built text widget.
            font_weight: Font weight applied when ``text`` is a string.
            spacing: Pixels between icon and text.
            margins: Outer layout margins (left, top, right, bottom).
        """
        # Initialize parent QWidget
        super().__init__(parent)

        self.setObjectName("leading-icon-label")

        self.texts = LeadingIconLabel.Text(text=text if isinstance(text, str) else None)

        if icon is None:
            raise ValueError("icon cannot be None")
        if not isinstance(icon, GenericIcons | OperatingSystemIcons | ApplicationIcons):
            raise ValueError(
                "icon must be a GenericIcons | OperatingSystemIcons | ApplicationIcons"
            )

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons = icon

        layout = QHBoxLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)  # Spacing between icon and text

        svg = SVG(icon_qt_path(self._icon), self)
        svg.setObjectName("leading-icon")
        svg.setFixedSize(
            get_svg_size(Settings.FONT.SIZE_DEFAULT)
        )  # Set the size of the leading icon depending on the font size

        layout.addWidget(svg)

        if isinstance(text, str):
            label = QLabel(text, self)
        else:
            label = text
        label.setObjectName("label")
        label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_DEFAULT,
                QFont.Weight.Normal,
            )
        )

        layout.addWidget(label)

        self.setLayout(layout)

        self.ui: LeadingIconLabel.UI = LeadingIconLabel.UI(svg=svg, text=label)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Set the size policy for elements composing the leading icon label."""
        self.ui.svg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _set_alignment(self) -> None:
        """Set the alignment for elements composing the leading icon label."""
        self.ui.svg.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.layout().setAlignment(
            self.ui.svg, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.ui.text.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.layout().setAlignment(
            self.ui.text, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )

    def _connect_signals(self) -> None:
        """Connect signals for elements composing the leading icon label."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme icons to elements composing the leading icon label."""
        self.ui.svg.set_path(icon_qt_path_for_theme(theme, self._icon))

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons
    ) -> None:
        """Set the leading icon path.

        Args:
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons.
        """
        if icon is None:
            return
        if not isinstance(icon, GenericIcons | OperatingSystemIcons | ApplicationIcons):
            raise ValueError(
                "icon must be a GenericIcons | OperatingSystemIcons | ApplicationIcons"
            )
        self._icon = icon
        self.ui.svg.set_path(icon_qt_path(self._icon))

    def set_text(self, text: QLabel | str | None = None) -> None:
        """Set the text of the leading icon label.

        Args:
            text: Text string or pre-built text widget.
        """
        if text is None:
            return
        if isinstance(text, str):
            self.texts = LeadingIconLabel.Text(text=text)
            self.ui.text.setText(text)
            return

        layout = self.layout()
        layout.removeWidget(self.ui.text)
        self.ui.text.deleteLater()

        text.setParent(self)
        text.setObjectName("label")
        layout.addWidget(text)
        self.ui.text = text
        self.texts = LeadingIconLabel.Text(text=None)
        self._finalize_ui_hooks()
