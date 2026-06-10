"""Welcome connection actions block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import WalkthroughButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.wrapper import VerticalLayoutWrapper


class ConnectionActionsBlock(VerticalLayoutWrapper, Block):
    """Welcome card containing interactive but currently unwired connection buttons."""

    texts: ConnectionActionsBlock.Text
    ui: ConnectionActionsBlock.UI

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Connect your device"
        wifi_button: Final[str] = "Wi-Fi pairing"
        usb_button: Final[str] = "USB cable"

    @dataclass
    class UI:
        title: QLabel
        wifi_button: WalkthroughButton
        usb_button: WalkthroughButton
        buttons_wrapper: VerticalLayoutWrapper
        body_wrapper: VerticalLayoutWrapper

    def __init__(self, parent: QWidget | None = None) -> None:
        block_texts = ConnectionActionsBlock.Text()

        title = QLabel(block_texts.title, parent)
        title.setProperty("welcome-section-title", True)

        wifi_button = WalkthroughButton(
            parent,
            block_texts.wifi_button,
            leading_icon=GenericIcons.WIFI,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        wifi_button.setProperty("welcome-connection-button", True)
        wifi_button.setToolTip("Prepare wireless Android pairing")

        usb_button = WalkthroughButton(
            parent,
            block_texts.usb_button,
            leading_icon=GenericIcons.USB,
            trailing_icon=GenericIcons.HAND_INDEX,
        )
        usb_button.setProperty("welcome-connection-button", True)
        usb_button.setToolTip("Prepare wired Android connection")

        buttons_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[wifi_button, usb_button],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        buttons_wrapper.setObjectName("connection-actions-wrapper")

        body_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[buttons_wrapper],
            spacing=Settings.SPACING.NONE,
            margins=Settings.SPACING.MARGIN_NONE,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        body_wrapper.setObjectName("connection-actions-body")

        super().__init__(
            parent,
            widgets=[title, body_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                Settings.WELCOME.CARD_PADDING_LEFT,
                Settings.WELCOME.CARD_PADDING_TOP,
                Settings.WELCOME.CARD_PADDING_RIGHT,
                Settings.WELCOME.CARD_PADDING_BOTTOM,
            ),
        )
        self.setObjectName("welcome-connection-actions-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts
        self.ui = ConnectionActionsBlock.UI(
            title=title,
            wifi_button=wifi_button,
            usb_button=usb_button,
            buttons_wrapper=buttons_wrapper,
            body_wrapper=body_wrapper,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.body_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.buttons_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.wifi_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.ui.usb_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

    def _set_alignment(self) -> None:
        self.ui.title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.body_wrapper.get_layout().setAlignment(
            self.ui.buttons_wrapper, Qt.AlignmentFlag.AlignTop
        )
        self.ui.buttons_wrapper.get_layout().setAlignment(Qt.AlignmentFlag.AlignTop)

    def _connect_signals(self) -> None:
        pass

    @property
    def wifi_button(self) -> WalkthroughButton:
        """Return the Wi-Fi connection button."""
        return self.ui.wifi_button

    @property
    def usb_button(self) -> WalkthroughButton:
        """Return the USB connection button."""
        return self.ui.usb_button

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.wifi_button.apply_theme_icons(theme)
        self.ui.usb_button.apply_theme_icons(theme)


__all__ = ["ConnectionActionsBlock"]
