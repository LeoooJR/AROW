"""OTP input components and validators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from gui.colors import Theme
from gui.components.base.component import Component
from gui.components.inputs.input_settings import input_settings
from gui.settings import Settings


class OTPType(Enum):
    """
    OTP type.
    """

    IP = "IP"
    PORT = "Port"
    ASSOCIATION_CODE = "Association Code"


class OTPValidator(Enum):
    """
    OTP validator.
    """

    IP = QIntValidator()
    PORT = QIntValidator(0, 9)
    ASSOCIATION_CODE = QIntValidator(0, 9)


class OTPLineEdit(QLineEdit, Component):
    """
    QLineEdit subclass to handle backspace focus navigation and paste event for autofill.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on a single OTP cell."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the OTP cell."""

        pass

    def __init__(self, owner, index, *args, **kwargs):
        """Single OTP digit field wired to a parent ``OTPInput``.

        Args:
            owner: Parent ``OTPInput`` coordinating focus and paste.
            index: Zero-based cell index within the OTP sequence.
            *args: Forwarded to ``QLineEdit`` (typically parent).
            **kwargs: Forwarded to ``QLineEdit``.
        """
        super().__init__(*args, **kwargs)
        self.texts = OTPLineEdit.Text()
        self.ui = OTPLineEdit.UI()
        self._otp_parent = owner
        self._otp_index = index
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace:
            cursor_pos = self.cursorPosition()
            if cursor_pos == 0 and (not QLineEdit.text(self)) and self._otp_index > 0:
                # Move focus to previous field if not first field and field is empty
                prev_input = self._otp_parent._otp_inputs[self._otp_index - 1]
                prev_input.setFocus()
                prev_input.setCursorPosition(len(prev_input.text()))
                event.accept()
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Override paste event to autofill OTP fields."""
        text = source.text()
        if not text:
            return
        parent = self._otp_parent
        max_length = parent._max_length
        start_idx = self._otp_index
        idx = 0
        for i in range(start_idx, len(parent._otp_inputs)):
            current_len = max_length[i]
            chunk = text[idx : idx + current_len]
            parent._otp_inputs[i].setText(chunk)
            idx += len(chunk)
            if idx >= len(text):
                break
        # Optionally, move focus to next empty field (better UX)
        for i in range(start_idx, len(parent._otp_inputs)):
            if parent._otp_inputs[i].text() == "":
                parent._otp_inputs[i].setFocus()
                break
        else:
            parent._otp_inputs[-1].setFocus()


class OTPInput(QWidget, Component):
    """
    OTP input widget.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the OTP composite."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the OTP composite."""

        pass

    def __init__(
        self,
        parent: QWidget = None,
        otp_type: OTPType = OTPType.IP,
        otp_length: int = 6,
        max_length: list[int] = [1, 1, 1, 1, 1, 1],
        echo_mode: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal,
    ):
        """Lay out a row of validated OTP cells.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            otp_type: Validation and grouping mode (IP, port, or association code).
            otp_length: Number of digit boxes.
            max_length: Per-cell max lengths; length must match ``otp_length``.
            echo_mode: Echo mode forwarded to each ``QLineEdit``.
        """
        if len(max_length) != otp_length:
            raise ValueError(
                "Max length list must be the same length as the OTP length"
            )
        super().__init__(parent)
        self.texts = OTPInput.Text()
        self.ui = OTPInput.UI()

        self.setObjectName("otp-input")
        self._otp_type = otp_type
        self._otp_length = otp_length
        self._max_length = max_length
        self._echo_mode = echo_mode
        self._otp_inputs: list[QLineEdit] = []
        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.XS)

        for i in range(self._otp_length):
            otp_input = OTPLineEdit(self, i, self)
            otp_input.setObjectName(f"otp-input-{i}")
            otp_input.setFrame(True)
            otp_input.setFixedSize(
                input_settings.OTP.INPUT_SIZE, input_settings.OTP.INPUT_SIZE
            )
            otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
            otp_input.setCursor(Qt.CursorShape.IBeamCursor)
            otp_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            otp_input.setEchoMode(self._echo_mode)
            otp_input.setMaxLength(self._max_length[i])
            otp_input.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly)
            if otp_type == OTPType.IP:
                otp_input.setValidator(OTPValidator.IP.value)
            elif otp_type == OTPType.PORT:
                otp_input.setValidator(OTPValidator.PORT.value)
            elif otp_type == OTPType.ASSOCIATION_CODE:
                otp_input.setValidator(OTPValidator.ASSOCIATION_CODE.value)
            otp_input.textChanged.connect(
                lambda text, idx=i: self._on_otp_text_changed(idx, text)
            )

            layout.addWidget(otp_input)
            self._otp_inputs.append(otp_input)

        self.setLayout(layout)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _on_otp_text_changed(self, index: int, text: str) -> None:
        if index < self._otp_length - 1 and len(text) == self._max_length[index]:
            self._otp_inputs[index + 1].setFocus()

    def is_valid(self) -> bool:
        for otp_input in self._otp_inputs:
            if not otp_input.hasAcceptableInput():
                return False
        return True

    def get_invalid_index(self) -> set[int]:
        invalid_indices_by_type: set[int] = set()
        invalid_indices_by_length: set[int] = set()
        for i, otp_input in enumerate(self._otp_inputs):
            if len(otp_input.text()) < self._max_length[i]:
                invalid_indices_by_length.add(i)
            if not otp_input.hasAcceptableInput():
                invalid_indices_by_type.add(i)
        return invalid_indices_by_type | invalid_indices_by_length

    def text(self) -> str:
        """Get the text of the OTP input. If the OTP type is IP, return the IP address. If the OTP type is PORT, return the port number. If the OTP type is ASSOCIATION_CODE, return the association code."""
        if self._otp_type == OTPType.IP:
            return ".".join([otp_input.text() for otp_input in self._otp_inputs])
        elif self._otp_type == OTPType.PORT:
            return "".join([otp_input.text() for otp_input in self._otp_inputs])
        elif self._otp_type == OTPType.ASSOCIATION_CODE:
            return "".join([otp_input.text() for otp_input in self._otp_inputs])
        else:
            return ""

    def clear(self) -> None:
        """Clear the OTP inputs."""
        for otp_input in self._otp_inputs:
            otp_input.clear()
