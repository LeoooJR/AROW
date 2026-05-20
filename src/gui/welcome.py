from dataclasses import dataclass, field
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from gui import faker as ui_faker
from gui.colors import Theme
from gui.components import File, Image, WalkthroughButton
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class WelcomePanel(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Copy for the welcome hero, sections, walkthrough buttons, and recent placeholders."""

        tagline: Final[str] = (
            "Connect your Android device and simulate GPS location from your computer."
        )
        start_label: Final[str] = "Start"
        recent_label: Final[str] = "Recent"
        walkthrough_label: Final[str] = "Walkthrough"
        walkthrough_wifi_button: Final[str] = "Connect phone over Wi-Fi (Android >= 11)"
        walkthrough_usb_button: Final[str] = "Connect phone with USB (Android < 11)"
        recent_files: tuple[tuple[str, str], tuple[str, str], tuple[str, str]] = field(
            default_factory=ui_faker.generate_recent_file_triples
        )

    @dataclass
    class UI:
        """Composed widgets for the welcome screen layout."""

        image: Image
        tagline: QLabel
        hero: VerticalLayoutWrapper
        start_label: QLabel
        recent_label: QLabel
        recent_files_wrapper: VerticalLayoutWrapper
        walkthrough_label: QLabel
        walkthrough_wifi_button: WalkthroughButton
        walkthrough_usb_button: WalkthroughButton
        walkthrough_buttons_wrapper: VerticalLayoutWrapper
        start_card: VerticalLayoutWrapper
        walkthrough_card: VerticalLayoutWrapper
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

        start_label = QLabel(self.texts.start_label, self)
        start_label.setProperty("welcome-section-title", True)

        recent_label = QLabel(self.texts.recent_label, self)
        recent_label.setProperty("welcome-section-title", True)

        recent_files_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[recent_label],
            spacing=Settings.SPACING.XS,
        )
        self._add_recent_placeholders(recent_files_wrapper, count=3)

        start_card = VerticalLayoutWrapper(
            self,
            widgets=[start_label, recent_files_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                Settings.WELCOME.CARD_PADDING_LEFT,
                Settings.WELCOME.CARD_PADDING_TOP,
                Settings.WELCOME.CARD_PADDING_RIGHT,
                Settings.WELCOME.CARD_PADDING_BOTTOM,
            ),
            stretch_at_end=True,
        )
        start_card.setObjectName("welcome-start-card")
        start_card.setProperty("welcome-card", True)

        walkthrough_label = QLabel(self.texts.walkthrough_label, self)
        walkthrough_label.setProperty("welcome-section-title", True)

        walkthrough_wifi_button = WalkthroughButton(
            self,
            self.texts.walkthrough_wifi_button,
            leading_icon=OperatingSystemIcons.ANDROID,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        walkthrough_usb_button = WalkthroughButton(
            self,
            self.texts.walkthrough_usb_button,
            leading_icon=OperatingSystemIcons.ANDROID,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        walkthrough_buttons_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[walkthrough_wifi_button, walkthrough_usb_button],
            spacing=Settings.PANEL.SECTION_SPACING,
        )

        walkthrough_card = VerticalLayoutWrapper(
            self,
            widgets=[walkthrough_label, walkthrough_buttons_wrapper],
            spacing=Settings.SPACING.XS,
            margins=(
                Settings.WELCOME.CARD_PADDING_LEFT,
                Settings.WELCOME.CARD_PADDING_TOP,
                Settings.WELCOME.CARD_PADDING_RIGHT,
                Settings.WELCOME.CARD_PADDING_BOTTOM,
            ),
            stretch_at_end=True,
        )
        walkthrough_card.setObjectName("welcome-walkthrough-card")
        walkthrough_card.setProperty("welcome-card", True)

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
            start_label=start_label,
            recent_label=recent_label,
            recent_files_wrapper=recent_files_wrapper,
            walkthrough_label=walkthrough_label,
            walkthrough_wifi_button=walkthrough_wifi_button,
            walkthrough_usb_button=walkthrough_usb_button,
            walkthrough_buttons_wrapper=walkthrough_buttons_wrapper,
            start_card=start_card,
            walkthrough_card=walkthrough_card,
            sections_wrapper=sections_wrapper,
        )

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.image.set_pixmap_path(
            icon_qt_path_for_theme(theme, ApplicationIcons.LOGO_UI)
        )
        self.ui.walkthrough_wifi_button.apply_theme_icons(theme)
        self.ui.walkthrough_usb_button.apply_theme_icons(theme)
        lay = self.ui.recent_files_wrapper.get_layout()
        for i in range(lay.count()):
            item = lay.itemAt(i)
            w = item.widget() if item is not None else None
            if isinstance(w, File):
                w.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the welcome panel."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the welcome panel and its UI widgets."""
        pass

    def _add_recent_placeholders(
        self, recent_files_wrapper: VerticalLayoutWrapper, count: int = 3
    ) -> None:
        """
        Visual-only placeholders shown under the "Recent" label.
        No selection/click logic is implemented for these placeholder elements.

        Args:
            recent_files_wrapper: Vertical wrapper that owns the placeholder rows.
            count: Maximum number of placeholder file rows to add.
        """
        placeholder_items = self.texts.recent_files
        for i in range(min(count, len(placeholder_items))):
            file_name, file_type = placeholder_items[i]
            recent_files_wrapper.add_widget(
                File(
                    recent_files_wrapper,
                    file_name=file_name,
                    file_type=file_type,
                    file_save=False,
                )
            )

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.hero.get_layout().setAlignment(
            self.ui.image, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.hero.get_layout().setAlignment(
            self.ui.tagline, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.start_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.recent_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.walkthrough_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.recent_files_wrapper.get_layout().setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
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
        self.ui.start_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.recent_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.walkthrough_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.walkthrough_buttons_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.walkthrough_wifi_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.ui.walkthrough_usb_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
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
        self.ui.recent_files_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
