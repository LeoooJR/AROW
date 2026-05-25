"""Welcome walkthrough block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import WalkthroughButton
from gui.icons import GenericIcons, OperatingSystemIcons
from gui.settings import Settings
from gui.wrapper import VerticalLayoutWrapper


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
        """Build the welcome walkthrough card and its action rows."""
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
        """Set resize behavior for the walkthrough card and buttons."""
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
        """Align the walkthrough section title to the top-left."""
        self.ui.walkthrough_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

    def _connect_signals(self) -> None:
        """Connect block signals; walkthrough actions are currently static."""
        pass

    @property
    def walkthrough_wifi_button(self) -> WalkthroughButton:
        """Return the Wi-Fi walkthrough button."""
        return self.ui.walkthrough_wifi_button

    @property
    def walkthrough_usb_button(self) -> WalkthroughButton:
        """Return the USB walkthrough button."""
        return self.ui.walkthrough_usb_button

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh leading and trailing icons on walkthrough buttons."""
        self.ui.walkthrough_wifi_button.apply_theme_icons(theme)
        self.ui.walkthrough_usb_button.apply_theme_icons(theme)


__all__ = ["WalkthroughBlock"]
