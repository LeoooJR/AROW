from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from gui.blocks.start import StartRecentBlock, WalkthroughBlock
from gui.colors import Theme
from gui.components import Image
from gui.icons import ApplicationIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class WelcomePanel(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Copy for the welcome hero, sections, walkthrough buttons, and recent placeholders."""

        tagline: Final[str] = (
            "Connect your Android device and simulate GPS location from your computer."
        )

    @dataclass
    class UI:
        """Composed widgets for the welcome screen layout."""

        image: Image
        tagline: QLabel
        hero: VerticalLayoutWrapper
        start_card: StartRecentBlock
        walkthrough_card: WalkthroughBlock
        sections_wrapper: HorizontalLayoutWrapper

    def __init__(self, parent=None):
        """Build hero, start/recent, and walkthrough sections.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """

        super().__init__(parent)

        self.texts = WelcomePanel.Text()

        self.setObjectName("welcome-panel")
        self.setProperty("welcome-panel", True)

        image = Image(self, icon_qt_path(ApplicationIcons.LOGO_UI))
        image.setFixedSize(
            Settings.DIMENSION.WELCOME_LOGO_SIZE, Settings.DIMENSION.WELCOME_LOGO_SIZE
        )

        tagline = QLabel(self.texts.tagline, self)
        tagline.setWordWrap(True)
        tagline.setProperty("welcome-tagline", True)

        hero = VerticalLayoutWrapper(
            self,
            widgets=[image, tagline],
            spacing=Settings.WELCOME.HERO_ELEMENT_SPACING,
            margins=(0, 0, 0, 0),
        )
        hero.setObjectName("welcome-hero")
        hero.get_layout().setStretchFactor(tagline, 1)

        start_card = StartRecentBlock(self)
        walkthrough_card = WalkthroughBlock(self)

        sections_wrapper = HorizontalLayoutWrapper(
            self,
            widgets=[start_card, walkthrough_card],
            spacing=Settings.PANEL.SECTION_SPACING,
        )
        sections_wrapper.setObjectName("sections-wrapper")
        sl = sections_wrapper.get_layout()
        sl.setStretchFactor(start_card, 1)
        sl.setStretchFactor(walkthrough_card, 1)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(Settings.SPACING.XS)
        layout.addWidget(hero)
        layout.addWidget(sections_wrapper)
        self.setLayout(layout)

        self.ui: WelcomePanel.UI = WelcomePanel.UI(
            image=image,
            tagline=tagline,
            hero=hero,
            start_card=start_card,
            walkthrough_card=walkthrough_card,
            sections_wrapper=sections_wrapper,
        )

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.image.set_pixmap_path(
            icon_qt_path_for_theme(theme, ApplicationIcons.LOGO_UI)
        )
        self.ui.start_card.apply_theme_icons(theme)
        self.ui.walkthrough_card.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the welcome panel."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the welcome panel and its UI widgets."""
        pass

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.hero.get_layout().setAlignment(
            self.ui.image, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.hero.get_layout().setAlignment(
            self.ui.tagline, Qt.AlignmentFlag.AlignCenter
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.ui.hero.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.image.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.tagline.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.ui.start_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.walkthrough_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.sections_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
