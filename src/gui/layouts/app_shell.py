"""Top-level application shell below the native window frame."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque, Final

from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget
from shiboken6 import isValid

from gui.blocks.top_bar import TopBar
from gui.components import QuestionDialog, Toast
from gui.constants.colors import Theme, get_current_palette
from gui.constants.icons import GenericIcons
from gui.layouts.workspace import WorkspaceLayout
from gui.signals import signals
from logger import logger


class AppShell(QWidget):
    """Compose application chrome, routed workspace, dialogs, and toasts."""

    @dataclass(frozen=True)
    class Text:
        add_device_dialog_title: Final[str] = "Adding a device"
        add_device_dialog_text: Final[str] = "Do you want to add a new device?"
        add_device_dialog_detailed_text: Final[str] = (
            "This action will add a new device to the list of available devices.\n"
            "Make sure the device is powered on, in developer mode and connected "
            "to the same network as the computer.\n"
            "You must own full ownership of the device to use it with this software."
        )
        connecting_to_device_toast: Final[str] = (
            "Trying to connect to device... Please wait."
        )

    @dataclass
    class UI:
        header: TopBar
        workspace: WorkspaceLayout
        toast: Toast | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.texts = AppShell.Text()
        self._toast_queue: Deque[tuple[str, str]] = deque()

        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.Window, QColor(get_current_palette().CANVAS)
        )
        self.setPalette(palette)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = TopBar(self)
        workspace = WorkspaceLayout(self)
        layout.addWidget(header)
        layout.addWidget(workspace, 1)
        self.setLayout(layout)

        self.ui = AppShell.UI(header=header, workspace=workspace)
        self._connect_signals()

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.header.apply_theme_icons(theme)
        self.ui.workspace.apply_theme_icons(theme)

    def _connect_signals(self) -> None:
        signals.UI.DisplayLeftPanelsRequested.connect(self._display_left_panels)
        signals.UI.HideLeftPanelsRequested.connect(self._hide_left_panels)
        signals.UI.DisplayRightPanelsRequested.connect(self._display_right_panels)
        signals.UI.HideRightPanelsRequested.connect(self._hide_right_panels)
        signals.DEVICE.AddDeviceRequested.connect(self._on_add_device_requested)
        signals.DEVICE.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )

    @Slot()
    def _display_left_panels(self) -> None:
        self.ui.workspace.set_left_panels_visibility(True)

    @Slot()
    def _hide_left_panels(self) -> None:
        self.ui.workspace.set_left_panels_visibility(False)

    @Slot()
    def _display_right_panels(self) -> None:
        self.ui.workspace.set_right_panels_visibility(True)

    @Slot()
    def _hide_right_panels(self) -> None:
        self.ui.workspace.set_right_panels_visibility(False)

    @Slot()
    def _on_add_device_requested(self) -> None:
        dialog = QuestionDialog(
            self,
            icon=GenericIcons.DEVICE,
            title=self.texts.add_device_dialog_title,
            text=self.texts.add_device_dialog_text,
            detailed_text=self.texts.add_device_dialog_detailed_text,
        )
        if dialog.exec() == QMessageBox.StandardButton.Yes:
            logger.info("Device pairing opened")
            signals.DEVICE.AuthentificationRequested.emit()
        else:
            logger.info("Device pairing cancelled before opening")
            signals.DEVICE.AuthentificationCancelled.emit()

    @Slot()
    def _on_authentification_confirmed(self) -> None:
        self.post_toast(self.texts.connecting_to_device_toast, level="info")

    def post_toast(self, text: str, level: str) -> None:
        """Enqueue a toast and display messages sequentially."""
        if not text:
            return
        if not self.isVisible():
            logger.debug("Toast skipped because the main container is hidden")
            return

        now = monotonic()
        last_payload = getattr(self, "_last_toast_payload", None)
        last_timestamp = getattr(self, "_last_toast_timestamp", 0.0)
        if last_payload == (text, level) and now - last_timestamp < 0.35:
            logger.debug("Duplicate toast skipped within debounce window")
            return
        self._last_toast_payload = (text, level)
        self._last_toast_timestamp = now
        self._toast_queue.append((text, level))
        self._show_next_toast()

    @Slot()
    def _show_next_toast(self) -> None:
        current_toast = self.ui.toast
        if (
            current_toast is not None
            and isValid(current_toast)
            and current_toast.isVisible()
        ):
            return
        self.ui.toast = None
        if not self._toast_queue:
            return
        text, level = self._toast_queue.popleft()
        try:
            toast = Toast(self, text, level)
            toast.destroyed.connect(self._on_active_toast_destroyed)
            self.ui.toast = toast
        except RuntimeError:
            logger.warning(
                "Toast display failed because its widget was deleted during creation"
            )
            QTimer.singleShot(0, self._show_next_toast)

    @Slot()
    def _on_active_toast_destroyed(self) -> None:
        self.ui.toast = None
        QTimer.singleShot(0, self._show_next_toast)
