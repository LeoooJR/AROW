"""Device authentification card component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from loguru import logger
from PySide6.QtCore import QElapsedTimer, Qt, QTimer, Slot
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import QFrame, QLineEdit, QSizePolicy, QVBoxLayout, QWidget

from gui.animation import apply_highlight_level, compute_sine_pulse_level
from gui.components.base.component import Component
from gui.components.buttons.button import Button
from gui.components.buttons.tool_button import ToolButton
from gui.components.containers.container_settings import container_settings
from gui.components.inputs.otp import OTPInput, OTPType
from gui.components.labels.demi_bold_text import DemiBoldText
from gui.components.labels.helper_text import HelperText
from gui.components.media import get_svg_size
from gui.components.media.svg import SVG
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons, icon_qt_path_for_theme
from gui.constants.settings import Settings
from gui.signals import signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class AuthentificationCard(QFrame, Component):
    """
    Card widget.
    """

    @dataclass(frozen=True)
    class Text:
        """Titles, descriptions, helper labels, and action copy for the card."""

        title: str | None = None
        description: str | None = None
        close_button_tooltip: Final[str] = "Close"
        helper_ip_otp_input: Final[str] = "IP address"
        helper_port_otp_input: Final[str] = "Port"
        helper_association_code_otp_input: Final[str] = "Association code"
        confirm_button: Final[str] = "Confirm"

    @dataclass
    class UI:
        """Composed widgets for credentials, OTP inputs, and confirm."""

        close_button: ToolButton
        icon: SVG
        icon_center_row: HorizontalLayoutWrapper
        icon_wrapper: HorizontalLayoutWrapper
        title: DemiBoldText
        description: HelperText
        helper_ip_otp_input: HelperText
        ip_otp_input: OTPInput
        ip_otp_input_wrapper: VerticalLayoutWrapper
        port_otp_input: OTPInput
        helper_port_otp_input: HelperText
        port_otp_input_wrapper: VerticalLayoutWrapper
        association_code_otp_input: OTPInput
        helper_association_code_otp_input: HelperText
        association_code_otp_input_wrapper: VerticalLayoutWrapper
        device_otp_wrapper: HorizontalLayoutWrapper
        confirm_button: Button

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str | None = None,
        icon_path: str | None = None,
        description: str | None = None,
    ):
        """Build the authentification card with OTP rows and confirm action.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            title: Card heading text.
            icon_path: Optional hero icon asset above the title.
            description: Supporting text under the title.
        """
        super().__init__(parent)

        self.texts = AuthentificationCard.Text(title=title, description=description)
        self.ui: AuthentificationCard.UI
        self.setObjectName("card")
        self.setProperty("authentification-card", True)
        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.XS)

        close_button = ToolButton(
            self,
            icon=GenericIcons.X,
            tooltip=self.texts.close_button_tooltip,
        )

        icon = SVG("", self)
        icon.hide()
        if icon_path:
            icon.set_path(icon_path)
            icon.setFixedSize(get_svg_size(Settings.FONT.SIZE_TITLE))
            icon.show()

        icon_center_row = HorizontalLayoutWrapper(
            self,
            margins=(0, Settings.SPACING.XS, 0, 0),
            widgets=[icon] if icon_path else [],
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        icon_wrapper = HorizontalLayoutWrapper(
            self, widgets=[icon_center_row, close_button]
        )
        icon_wrapper.get_layout().setStretch(0, 1)
        layout.addWidget(icon_wrapper, 1)

        title_label = DemiBoldText(self, title or "")
        if title:
            layout.addWidget(title_label)
        else:
            title_label.hide()

        description_label = HelperText(self, description or "")
        if description:
            layout.addWidget(description_label)
        else:
            description_label.hide()

        helper_ip_otp_input = HelperText(self, self.texts.helper_ip_otp_input)
        ip_otp_input = OTPInput(
            self,
            otp_type=OTPType.IP,
            otp_length=4,
            max_length=[3, 3, 1, 2],
            echo_mode=QLineEdit.EchoMode.Normal,
        )
        ip_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_ip_otp_input, ip_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        helper_port_otp_input = HelperText(self, self.texts.helper_port_otp_input)
        port_otp_input = OTPInput(
            self,
            otp_type=OTPType.PORT,
            otp_length=5,
            max_length=[1, 1, 1, 1, 1],
            echo_mode=QLineEdit.EchoMode.Normal,
        )
        port_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_port_otp_input, port_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        helper_association_code_otp_input = HelperText(
            self, self.texts.helper_association_code_otp_input
        )
        association_code_otp_input = OTPInput(
            self,
            otp_type=OTPType.ASSOCIATION_CODE,
            otp_length=6,
            max_length=[1, 1, 1, 1, 1, 1],
            echo_mode=QLineEdit.EchoMode.PasswordEchoOnEdit,
        )
        association_code_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_association_code_otp_input, association_code_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        device_otp_wrapper = HorizontalLayoutWrapper(
            self,
            widgets=[ip_otp_input_wrapper, port_otp_input_wrapper],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        layout.addWidget(device_otp_wrapper)
        layout.addWidget(association_code_otp_input_wrapper)

        confirm_button = Button(self, self.texts.confirm_button)
        layout.addWidget(confirm_button, 1)

        self.setLayout(layout)

        self.ui = AuthentificationCard.UI(
            close_button=close_button,
            icon=icon,
            icon_center_row=icon_center_row,
            title=title_label,
            icon_wrapper=icon_wrapper,
            description=description_label,
            helper_ip_otp_input=helper_ip_otp_input,
            ip_otp_input=ip_otp_input,
            ip_otp_input_wrapper=ip_otp_input_wrapper,
            port_otp_input=port_otp_input,
            helper_port_otp_input=helper_port_otp_input,
            port_otp_input_wrapper=port_otp_input_wrapper,
            association_code_otp_input=association_code_otp_input,
            helper_association_code_otp_input=helper_association_code_otp_input,
            association_code_otp_input_wrapper=association_code_otp_input_wrapper,
            device_otp_wrapper=device_otp_wrapper,
            confirm_button=confirm_button,
        )

        # Timers for invalid OTP highlight: smooth pulse (sine-driven level 0–10),
        # same timing family as device-list highlight.
        self._invalid_highlight_pulse_timer = QTimer(self)
        self._invalid_highlight_pulse_timer.setSingleShot(False)
        self._invalid_highlight_pulse_timer.timeout.connect(
            self._on_invalid_highlight_pulse_tick
        )
        self._invalid_highlight_stop_timer = QTimer(self)
        self._invalid_highlight_stop_timer.setSingleShot(True)
        self._invalid_highlight_stop_timer.timeout.connect(
            self.stop_invalid_otp_highlight
        )
        self._invalid_highlight_elapsed = QElapsedTimer()
        self._invalid_targets: dict[OTPInput, set[int]] = {}

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(container_settings.AUTHENTIFICATION_CARD.MIN_WIDTH)
        self.setMaximumWidth(container_settings.AUTHENTIFICATION_CARD.MAX_WIDTH)
        self.ui.close_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.icon_center_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.description.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.confirm_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.ip_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.port_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.association_code_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.device_otp_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        # self.layout().setAlignment(self.ui.icon_wrapper, Qt.AlignmentFlag.AlignCenter)
        icon_header_layout = self.ui.icon_wrapper.get_layout()
        icon_header_layout.setAlignment(
            self.ui.icon_center_row, Qt.AlignmentFlag.AlignTop
        )
        icon_header_layout.setAlignment(
            self.ui.close_button,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.ui.icon_center_row.get_layout().setAlignment(
            self.ui.icon,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )
        self.layout().setAlignment(self.ui.title, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(self.ui.description, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.ip_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.ip_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_ip_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.ip_otp_input_wrapper.get_layout().setAlignment(
            self.ui.ip_otp_input, Qt.AlignmentFlag.AlignLeft
        )
        self.layout().setAlignment(
            self.ui.port_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.port_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_port_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.port_otp_input_wrapper.get_layout().setAlignment(
            self.ui.port_otp_input, Qt.AlignmentFlag.AlignLeft
        )
        self.layout().setAlignment(
            self.ui.association_code_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.association_code_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_association_code_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.association_code_otp_input_wrapper.get_layout().setAlignment(
            self.ui.association_code_otp_input, Qt.AlignmentFlag.AlignLeft
        )

    def _connect_signals(self) -> None:
        self.ui.confirm_button.clicked.connect(self._on_confirm_button_clicked)
        self.ui.close_button.clicked.connect(self._on_close_button_clicked)

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.close_button.apply_theme_icons(theme)
        self.ui.icon.set_path(icon_qt_path_for_theme(theme, GenericIcons.DEVICE))

    ### Slots ###

    @Slot()
    def _on_close_button_clicked(self) -> None:
        """Handle the close button clicked event."""
        logger.info("Device pairing cancelled")
        signals.DEVICE.AuthentificationCancelled.emit()

    def _is_ip_otp_input_valid(self) -> bool:
        return self.ui.ip_otp_input.is_valid()

    def _is_port_otp_input_valid(self) -> bool:
        return self.ui.port_otp_input.is_valid()

    def _is_association_code_otp_input_valid(self) -> bool:
        return self.ui.association_code_otp_input.is_valid()

    @Slot()
    def _on_confirm_button_clicked(self) -> None:
        """Validate and submit the pairing form."""
        invalid_fields = tuple(
            field
            for field, valid in (
                ("ip", self._is_ip_otp_input_valid()),
                ("port", self._is_port_otp_input_valid()),
                ("association_code", self._is_association_code_otp_input_valid()),
            )
            if not valid
        )
        if not invalid_fields:
            ip = self.ui.ip_otp_input.text()
            port = self.ui.port_otp_input.text()
            association_code = self.ui.association_code_otp_input.text()
            logger.info(
                "Device pairing submitted",
                ip=ip,
                port=port,
                association_code=association_code,
            )
            signals.DEVICE.AuthentificationConfirmed.emit(
                ip,
                port,
                association_code,
            )
        else:
            logger.info(
                "Device pairing submission rejected",
                invalid_fields=invalid_fields,
            )
            self.start_invalid_otp_highlight()

    def _otp_sections(self) -> list[tuple[HelperText, OTPInput]]:
        return [
            (self.ui.helper_ip_otp_input, self.ui.ip_otp_input),
            (self.ui.helper_port_otp_input, self.ui.port_otp_input),
            (
                self.ui.helper_association_code_otp_input,
                self.ui.association_code_otp_input,
            ),
        ]

    def _set_invalid_otp_highlight_level(self, level: int) -> None:
        for helper_label, otp_group in self._otp_sections():
            invalid_indices = self._invalid_targets.get(otp_group, set())
            helper_level = level if invalid_indices else 0
            apply_highlight_level(
                helper_label, "otp-helper-invalid-highlight-level", helper_level
            )
            for i, otp_line_edit in enumerate(otp_group._otp_inputs):
                line_level = level if i in invalid_indices else 0
                apply_highlight_level(
                    otp_line_edit, "otp-invalid-highlight-level", line_level
                )

    @Slot()
    def _on_invalid_highlight_pulse_tick(self) -> None:
        cycle_ms = container_settings.ATTENTION_HIGHLIGHT.PULSE_CYCLE_MS
        elapsed = self._invalid_highlight_elapsed.elapsed()
        level = compute_sine_pulse_level(elapsed, cycle_ms)
        self._set_invalid_otp_highlight_level(level)

    def start_invalid_otp_highlight(self) -> None:
        """Start smooth error pulse on invalid OTP inputs and their helper labels."""
        self.stop_invalid_otp_highlight()
        self._invalid_targets = {}
        for _, otp_group in self._otp_sections():
            invalid_indices = set(otp_group.get_invalid_index())
            if invalid_indices:
                self._invalid_targets[otp_group] = invalid_indices
        if not self._invalid_targets:
            return
        self._invalid_highlight_elapsed.start()
        self._invalid_highlight_pulse_timer.start(
            container_settings.ATTENTION_HIGHLIGHT.UPDATE_MS
        )
        self._invalid_highlight_stop_timer.start(
            container_settings.ATTENTION_HIGHLIGHT.DURATION
        )

    @Slot()
    def stop_invalid_otp_highlight(self) -> None:
        """Stop OTP invalid highlight animation and restore default label/input styles."""
        self._invalid_highlight_pulse_timer.stop()
        self._invalid_highlight_stop_timer.stop()
        self._set_invalid_otp_highlight_level(0)

    def clear(self) -> None:
        """Clear the OTP inputs."""
        for _, otp_input in self._otp_sections():
            otp_input.clear()
        self.stop_invalid_otp_highlight()

    def showEvent(self, event: QShowEvent) -> None:
        """Clear the OTP inputs when the card is shown."""
        self.clear()
        super().showEvent(event)
