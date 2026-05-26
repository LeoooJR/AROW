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
from gui.components.media import get_svg_size


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
        font_size: int = Settings.FONT.SIZE_DEFAULT,
        font_weight: QFont.Weight = QFont.Weight.Normal,
        icon_size=None,
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
        text_alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
        properties: dict[str, object] | None = None,
        label_properties: dict[str, object] | None = None,
        constrain_to_size_hint: bool = False,
    ):
        """Lay out a leading SVG icon beside a string or external ``QLabel``.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons.
            text: Caption string or pre-built text widget.
            font_size: Font point size applied when ``text`` is a string.
            font_weight: Font weight applied when ``text`` is a string.
            icon_size: Fixed icon size; derived from ``font_size`` when omitted.
            spacing: Pixels between icon and text.
            margins: Outer layout margins (left, top, right, bottom).
            text_alignment: Alignment for the text label and its layout item.
            properties: Dynamic properties to apply to the root widget.
            label_properties: Dynamic properties to apply to the text label.
            constrain_to_size_hint: When True, cap the widget to its layout size hint.
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
        self._text_alignment = text_alignment
        self._properties = properties or {}
        self._label_properties = label_properties or {}

        if icon_size is None:
            icon_size = get_svg_size(font_size)

        layout = QHBoxLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)  # Spacing between icon and text

        svg = SVG(icon_qt_path(self._icon), self)
        svg.setObjectName("leading-icon")
        svg.setFixedSize(icon_size)

        layout.addWidget(svg)

        if isinstance(text, str):
            label = QLabel(text, self)
        else:
            label = text
        label.setObjectName("label")
        label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                font_size,
                font_weight,
            )
        )
        for key, value in self._label_properties.items():
            label.setProperty(key, value)

        for key, value in self._properties.items():
            self.setProperty(key, value)
        if self._properties:
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout.addWidget(label)

        self.setLayout(layout)
        if constrain_to_size_hint:
            self.setMaximumSize(layout.sizeHint())

        self.ui: LeadingIconLabel.UI = LeadingIconLabel.UI(svg=svg, text=label)

        self._finalize_ui_hooks()
        self._refresh_stylesheet_properties()

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
        self.ui.text.setAlignment(self._text_alignment)
        self.layout().setAlignment(self.ui.text, self._text_alignment)

    def _connect_signals(self) -> None:
        """Connect signals for elements composing the leading icon label."""
        pass

    def _refresh_stylesheet_properties(self) -> None:
        """Re-polish after dynamic property changes so Qt refreshes QSS selectors."""
        for widget in (self, self.ui.text):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

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
        for key, value in self._label_properties.items():
            text.setProperty(key, value)
        layout.addWidget(text)
        self.ui.text = text
        self.texts = LeadingIconLabel.Text(text=None)
        self._finalize_ui_hooks()
        self._refresh_stylesheet_properties()
