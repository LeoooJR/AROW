"""Authentication overlay displayed above the application shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from gui.components import AuthentificationCard
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons, icon_qt_path


class AuthenticationOverlay(QWidget):
    """Block shell interaction while collecting device credentials."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Authentification"
        description: Final[str] = "Please enter your access credentials to continue."

    @dataclass
    class UI:
        authentification_card: AuthentificationCard

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.texts = AuthenticationOverlay.Text()
        self.setObjectName("authentification-overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        card = AuthentificationCard(
            self,
            title=self.texts.title,
            icon_path=icon_qt_path(GenericIcons.DEVICE),
            description=self.texts.description,
        )
        layout.addWidget(card)
        layout.addStretch()
        self.setLayout(layout)
        self.ui = AuthenticationOverlay.UI(authentification_card=card)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.layout().setAlignment(card, Qt.AlignmentFlag.AlignCenter)

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.authentification_card.apply_theme_icons(theme)
