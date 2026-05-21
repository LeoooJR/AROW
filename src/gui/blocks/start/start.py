"""Start-screen blocks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui import faker as ui_faker
from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import File, WalkthroughButton
from gui.icons import GenericIcons, OperatingSystemIcons
from gui.settings import Settings
from gui.wrapper import VerticalLayoutWrapper


class StartRecentBlock(VerticalLayoutWrapper, Block):
    """Welcome start card containing recent-file placeholders."""

    @dataclass(frozen=True)
    class Text:
        start_label: Final[str] = "Start"
        recent_label: Final[str] = "Recent"
        recent_files: tuple[tuple[str, str], tuple[str, str], tuple[str, str]] = field(
            default_factory=ui_faker.generate_recent_file_triples
        )

    @dataclass
    class UI:
        start_label: QLabel
        recent_label: QLabel
        recent_files_wrapper: VerticalLayoutWrapper

    def __init__(self, parent: QWidget | None = None):
        block_texts = StartRecentBlock.Text()

        start_label = QLabel(block_texts.start_label, parent)
        start_label.setProperty("welcome-section-title", True)

        recent_label = QLabel(block_texts.recent_label, parent)
        recent_label.setProperty("welcome-section-title", True)

        recent_files_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[recent_label],
            spacing=Settings.SPACING.XS,
        )

        super().__init__(
            parent,
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
        self.setObjectName("welcome-start-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts

        self.ui = StartRecentBlock.UI(
            start_label=start_label,
            recent_label=recent_label,
            recent_files_wrapper=recent_files_wrapper,
        )
        self._add_recent_placeholders(count=3)
        self._finalize_ui_hooks()

    def _add_recent_placeholders(self, count: int = 3) -> None:
        placeholder_items = self.texts.recent_files
        for index in range(min(count, len(placeholder_items))):
            file_name, file_type = placeholder_items[index]
            self.ui.recent_files_wrapper.add_widget(
                File(
                    self.ui.recent_files_wrapper,
                    file_name=file_name,
                    file_type=file_type,
                    file_save=False,
                )
            )

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.start_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.recent_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.recent_files_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.ui.start_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.recent_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.recent_files_wrapper.get_layout().setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        lay = self.ui.recent_files_wrapper.get_layout()
        for index in range(lay.count()):
            item = lay.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, File):
                widget.apply_theme_icons(theme)


class WalkthroughBlock(VerticalLayoutWrapper, Block):
    """Welcome walkthrough card containing walkthrough actions."""

    @dataclass(frozen=True)
    class Text:
        walkthrough_label: Final[str] = "Walkthrough"
        walkthrough_wifi_button: Final[str] = "Connect phone over Wi-Fi (Android >= 11)"
        walkthrough_usb_button: Final[str] = "Connect phone with USB (Android < 11)"

    @dataclass
    class UI:
        walkthrough_label: QLabel
        walkthrough_wifi_button: WalkthroughButton
        walkthrough_usb_button: WalkthroughButton
        walkthrough_buttons_wrapper: VerticalLayoutWrapper

    def __init__(self, parent: QWidget | None = None):
        block_texts = WalkthroughBlock.Text()

        walkthrough_label = QLabel(block_texts.walkthrough_label, parent)
        walkthrough_label.setProperty("welcome-section-title", True)

        walkthrough_wifi_button = WalkthroughButton(
            parent,
            block_texts.walkthrough_wifi_button,
            leading_icon=OperatingSystemIcons.ANDROID,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        walkthrough_usb_button = WalkthroughButton(
            parent,
            block_texts.walkthrough_usb_button,
            leading_icon=OperatingSystemIcons.ANDROID,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        walkthrough_buttons_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[walkthrough_wifi_button, walkthrough_usb_button],
            spacing=Settings.PANEL.SECTION_SPACING,
        )

        super().__init__(
            parent,
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
        self.setObjectName("welcome-walkthrough-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts

        self.ui = WalkthroughBlock.UI(
            walkthrough_label=walkthrough_label,
            walkthrough_wifi_button=walkthrough_wifi_button,
            walkthrough_usb_button=walkthrough_usb_button,
            walkthrough_buttons_wrapper=walkthrough_buttons_wrapper,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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

    def _set_alignment(self) -> None:
        self.ui.walkthrough_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.walkthrough_wifi_button.apply_theme_icons(theme)
        self.ui.walkthrough_usb_button.apply_theme_icons(theme)
