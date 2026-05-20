"""Welcome walkthrough card button component."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

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


class WalkthroughButton(QPushButton, Component):
    """
    Welcome walkthrough row styled as a large, soft card: lead icon (left, vertically centered),
    helper-colored text, small hand-index-style icon pinned to the top-right.
    Uses an internal layout (not QPushButton text/icon) so spacing matches the design reference.
    """

    @dataclass(frozen=True)
    class Text:
        """Walkthrough row label text."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the walkthrough button."""

        leading_svg: SVG
        label: QLabel
        trailing_svg: SVG

    def __init__(
        self,
        parent: QWidget | None,
        text: str,
        leading_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
        trailing_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
    ):
        """Build the custom walkthrough card button layout.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Main descriptive label (word-wrapped).
            leading_icon: Left column SVG asset.
            trailing_icon: Top-right hint SVG asset.
        """
        super().__init__(parent)

        self.texts = WalkthroughButton.Text(label=text)

        self.setObjectName("welcome-walkthrough-button")
        self.setProperty("welcome-walkthrough-button", True)

        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        pad_h = Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_PADDING_H
        pad_v = Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_PADDING_V
        row = QHBoxLayout(self)
        row.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        row.setSpacing(Settings.SPACING.SM)

        self._leading_icon = leading_icon
        lead_px = get_svg_size(Settings.FONT.SIZE_HELPER)
        leading_svg = SVG(icon_qt_path(leading_icon), self)
        leading_svg.setObjectName("walkthrough-card-lead-icon")
        leading_svg.setFixedSize(lead_px)

        label = QLabel(text, self)
        label.setObjectName("walkthrough-card-label")
        label.setWordWrap(True)

        trailing_host = QWidget(self)
        trailing_host.setObjectName("walkthrough-card-trailing")
        trailing_col = QVBoxLayout(trailing_host)
        trailing_col.setContentsMargins(0, 0, 0, 0)
        trailing_col.setSpacing(0)

        self._trailing_icon = trailing_icon
        trail_px = max(get_svg_size(Settings.FONT.SIZE_HELPER).width(), 20)
        trailing_svg = SVG(icon_qt_path(trailing_icon), self)
        trailing_svg.setObjectName("walkthrough-card-trail-icon")
        trailing_svg.setFixedSize(trail_px, trail_px)

        trailing_col.addWidget(
            trailing_svg, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        trailing_col.addStretch(1)

        row.addWidget(leading_svg, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label, 1)
        row.addWidget(
            trailing_host, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

        self.ui = WalkthroughButton.UI(
            leading_svg=leading_svg, label=label, trailing_svg=trailing_svg
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setMinimumHeight(Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        self.ui.leading_svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.ui.trailing_svg.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh walkthrough row SVGs for the given palette."""
        self.ui.leading_svg.set_path(icon_qt_path_for_theme(theme, self._leading_icon))
        self.ui.trailing_svg.set_path(
            icon_qt_path_for_theme(theme, self._trailing_icon)
        )
