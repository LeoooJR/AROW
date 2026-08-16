"""Device pairing page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout, QWidget

from gui.components import LeadingIconLabel
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons
from gui.constants.settings import Settings
from gui.wrapper import HorizontalLayoutWrapper


class DevicePage(QFrame):
    """Page that hosts the device pairing workflow."""

    @dataclass(frozen=True)
    class Text:
        """Copy for the device pairing page."""

        title: Final[str] = "Pairing Device"

    @dataclass
    class UI:
        """Chrome and body regions for pairing-specific content."""

        title: LeadingIconLabel
        header: HorizontalLayoutWrapper
        body: HorizontalLayoutWrapper

    def __init__(self, parent: QWidget | None = None):
        """Create the pairing page shell."""
        super().__init__(parent)

        self.ui: DevicePage.UI
        self.texts = DevicePage.Text()

        self.setObjectName("device-pairing-panel")
        self.setProperty("panel", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(Settings.PANEL.SECTION_SPACING)

        title = LeadingIconLabel(
            parent=None,
            icon=GenericIcons.DEVICE,
            text=self.texts.title,
            font_size=Settings.FONT.SIZE_TITLE,
            font_weight=QFont.Weight.DemiBold,
            spacing=Settings.PANEL.TITLE_ICON_SPACING,
            margins=(
                Settings.PANEL.TITLE_PADDING_LEFT,
                Settings.PANEL.TITLE_PADDING_TOP,
                Settings.PANEL.TITLE_PADDING_RIGHT,
                Settings.PANEL.TITLE_PADDING_BOTTOM,
            ),
            text_alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            properties={"panel-title": True, "main-panel-title": True},
            label_properties={"section-title": True},
            constrain_to_size_hint=True,
        )

        header = HorizontalLayoutWrapper(
            self,
            widgets=[title],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(header, 0)

        body = HorizontalLayoutWrapper(
            self,
            widgets=[],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        layout.addWidget(body, 1)

        self.setLayout(layout)
        self.ui = DevicePage.UI(title=title, header=header, body=body)
        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh page icons for ``theme``."""
        self.ui.title.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.layout().setAlignment(self.ui.header, Qt.AlignmentFlag.AlignLeft)
        self.ui.header.get_layout().setAlignment(
            self.ui.title, Qt.AlignmentFlag.AlignLeft
        )
