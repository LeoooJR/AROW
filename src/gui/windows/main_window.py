"""Main application window and controller-facing view facade."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PySide6.QtCore import QSize, Slot
from PySide6.QtGui import QColor, QFont, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

import gui.ressources_rc  # noqa: F401
from gui import __application__
from gui.components import QuestionDialog
from gui.constants.colors import Theme, get_current_palette, set_current_theme
from gui.constants.icons import (
    ApplicationIcons,
    GenericIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
    icons_need_theme_updates,
)
from gui.constants.settings import Settings
from gui.constants.stylesheet import stylesheet, stylesheet_dark, stylesheet_light
from gui.event_filter import ActivityTracker
from gui.layouts import AppShell
from gui.overlays import AuthenticationOverlay
from gui.signals import signals
from logger import logger

_OFFSCREEN_PLATFORM_NAME: Final[str] = "offscreen"
_OFFSCREEN_SCREEN_SIZE_ENV: Final[str] = "AROW_GUI_TEST_SCREEN_SIZE"
_DEFAULT_OFFSCREEN_SCREEN_SIZE: Final[QSize] = QSize(1800, 1000)


def _is_offscreen_platform() -> bool:
    """Return True when Qt is explicitly configured for headless rendering."""
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        == _OFFSCREEN_PLATFORM_NAME
    )


def _offscreen_screen_size_from_env() -> QSize:
    """Parse the optional offscreen screenshot size, falling back on malformed values."""
    raw = os.environ.get(_OFFSCREEN_SCREEN_SIZE_ENV, "").strip().lower()
    if not raw:
        return QSize(_DEFAULT_OFFSCREEN_SCREEN_SIZE)
    try:
        width_text, height_text = raw.split("x", maxsplit=1)
        width = int(width_text)
        height = int(height_text)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid offscreen screen size; using fallback",
            env_var=_OFFSCREEN_SCREEN_SIZE_ENV,
            raw=raw,
        )
        return QSize(_DEFAULT_OFFSCREEN_SCREEN_SIZE)
    if (
        width < Settings.DIMENSION.WINDOW_MIN_WIDTH
        or height < Settings.DIMENSION.WINDOW_MIN_HEIGHT
    ):
        logger.warning(
            "Offscreen screen size is below the minimum; using fallback",
            env_var=_OFFSCREEN_SCREEN_SIZE_ENV,
            raw=raw,
            min_width=Settings.DIMENSION.WINDOW_MIN_WIDTH,
            min_height=Settings.DIMENSION.WINDOW_MIN_HEIGHT,
        )
        return QSize(_DEFAULT_OFFSCREEN_SCREEN_SIZE)
    return QSize(width, height)


def _main_window_screen_size() -> QSize:
    """Resolve the screen size used to initialize ``MainWindow``."""
    if _is_offscreen_platform():
        return _offscreen_screen_size_from_env()
    screen = QApplication.primaryScreen()
    if screen is not None:
        return screen.availableSize()
    raise RuntimeError("MainWindow requires a primary screen outside offscreen mode.")


class MainWindow(QMainWindow):
    """
    Main window of the application.
    """

    @dataclass(frozen=True)
    class Text:
        """Window title, dialogs, and toast templates for the main window."""

        window_title: Final[str] = f"{__application__} - Main Window"
        connect_device_dialog_title: Final[str] = "Connecting to device"
        connect_device_dialog_text: str = "Do you want to connect to {device} device?"
        connect_device_dialog_detailed_text: str = (
            "This action will connect to the {device} device.\n"
            "Make sure the device is powered on, in developer mode and connected to the same network as the computer.\n"
            "You must own full ownership of the device to use it with this software."
        )
        authentification_success_toast: str = (
            "Successfully connected to device: {device}."
        )
        authentification_failed_toast: str = (
            "Failed to authentificate device: {ip}:{port} with association code: {association_code}: {reason}."
        )
        device_selection_failed_toast: str = "Failed to select device: {device}."
        device_selection_success_toast: str = "Successfully selected device: {device}."
        active_device_removed_success_toast: str = (
            "Successfully removed active device: {device}. Shutting down simulation..."
        )
        active_device_removed_error_toast: str = (
            "Failed to remove active device: {device}. Please try again."
        )
        map_render_failed_toast: str = (
            "Failed to render map for simulation {simulation_id}: {reason}."
        )
        simulation_location_rejected_toast: str = (
            "Invalid map location for marker {km} on line {line_code}-{line_troncon}: {reason}."
        )

    @dataclass
    class UI:
        """Root widgets: main content container and optional authentification layer."""

        app_shell: AppShell
        authentication_overlay: AuthenticationOverlay

    def __init__(self):
        """Create the main window, layout, and signal wiring."""
        # Initialize parent QMainWindow
        super().__init__()

        self._device_selection_dialog_open: bool = False

        self.ui: MainWindow.UI
        self.texts = MainWindow.Text()

        self.setWindowTitle(self.texts.window_title)

        # Get available screen size. In offscreen screenshot tests, Qt may not
        # expose a primary screen, so a deterministic GUI-only fallback is used.
        screen_size = _main_window_screen_size()

        # Resize window to available screen size
        self.resize(screen_size)

        # Set minimum size from settings
        self.setMinimumSize(
            QSize(
                Settings.DIMENSION.WINDOW_MIN_WIDTH,
                Settings.DIMENSION.WINDOW_MIN_HEIGHT,
            )
        )

        # Set maximum size to available screen size
        self.setMaximumSize(screen_size)

        # Set font from settings, populating to children widgets
        self.setFont(QFont(Settings.FONT.FAMILY))

        # Set project-wide style sheet
        self.setStyleSheet(stylesheet)

        # Create activity tracker
        self._activity_tracker = ActivityTracker(self)

        # Install event filter on the main window
        self.installEventFilter(self._activity_tracker)

        # Create main container widget
        app_shell = AppShell(self)
        self.setObjectName("main-container")

        # Set window icon to logo
        self.setWindowIcon(QPixmap(icon_qt_path(ApplicationIcons.LOGO)))

        # Set the main container as the central widget to fill the window
        self.setCentralWidget(app_shell)

        # Create authentication overlay above the main container.
        # Parented to container so it covers only app content area and blocks interaction underneath.
        authentication_overlay = AuthenticationOverlay(app_shell)
        authentication_overlay.setGeometry(app_shell.rect())
        authentication_overlay.raise_()
        authentication_overlay.setVisible(False)

        self.ui = MainWindow.UI(
            app_shell=app_shell, authentication_overlay=authentication_overlay
        )

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the main window."""

        #### Signals for handling the palette update ####
        signals.UI.UpdatePaletteSignal.connect(self._on_palette_update)

        #### Signals for handling the idle state ####
        self._activity_tracker.became_idle.connect(self._on_idle)

        #### Signals for handling the authentification workflow ####
        signals.DEVICE.AuthentificationRequested.connect(
            self._on_authentification_requested
        )
        signals.DEVICE.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        signals.DEVICE.AuthentificationCancelled.connect(
            self._on_authentification_cancelled
        )

        #### Signals for handling the device selection workflow ####
        signals.DEVICE.DeviceSelectionRequested.connect(
            self._on_device_selection_requested
        )

    ### Slots ###

    @Slot(str)
    def _on_palette_update(self, theme: Theme) -> None:
        """Handle the palette update."""
        set_current_theme(theme)
        self.setStyleSheet(stylesheet_light if theme == "light" else stylesheet_dark)
        palette = self.ui.app_shell.palette()
        palette.setColor(
            QPalette.ColorRole.Window, QColor(get_current_palette().CANVAS)
        )
        self.ui.app_shell.setPalette(palette)
        self._refresh_theme_icons(theme)

    def _refresh_theme_icons(self, theme: Theme) -> None:
        """Repaint pixmap/icon widgets when assets differ per theme."""
        if not icons_need_theme_updates():
            return
        self.setWindowIcon(
            QPixmap(icon_qt_path_for_theme(theme, ApplicationIcons.LOGO))
        )
        self.ui.app_shell.apply_theme_icons(theme)
        self.ui.authentication_overlay.apply_theme_icons(theme)

    @Slot()
    def _on_idle(self) -> None:
        """Handle the idle state: run helper and highlight device lists to draw attention."""
        # self.ui.app_shell.wake_up()
        signals.UI.RunHelperAnimationRequested.emit()

    def forward_adb_server_started(self) -> None:
        """Forward the ADB server started signal."""
        signals.ADB_SERVER.ADBServerStarted.emit()

    def forward_adb_server_stopped(self) -> None:
        """Forward the ADB server stopped signal."""
        signals.ADB_SERVER.ADBServerStopped.emit()

    @Slot(str, str)
    def _on_device_selection_requested(self, device_id: str, device_name: str) -> None:
        """Handle the device selection request."""
        if device_id is None:
            return
        if self._device_selection_dialog_open:
            logger.debug(
                "Device selection ignored because the dialog is already open",
            )
            return
        self._device_selection_dialog_open = True
        dialog = QuestionDialog(
            self,
            icon=GenericIcons.DEVICE,
            title=self.texts.connect_device_dialog_title,
            text=self.texts.connect_device_dialog_text.format(device=device_name),
            detailed_text=self.texts.connect_device_dialog_detailed_text.format(
                device=device_name
            ),
        )
        try:
            button = dialog.exec()

            if button == QMessageBox.StandardButton.Yes:
                logger.info(
                    "Device selection confirmed",
                    device_id=device_id,
                    device_name=device_name,
                )
                signals.DEVICE.DeviceSelectionConfirmed.emit(device_id, device_name)
            else:
                logger.info(
                    "Device selection cancelled",
                    device_id=device_id,
                    device_name=device_name,
                )
                signals.DEVICE.DeviceSelectionCancelled.emit()
        finally:
            self._device_selection_dialog_open = False

    @Slot()
    def _on_authentification_requested(self) -> None:
        """Handle the authentification request."""
        self.ui.authentication_overlay.setGeometry(self.ui.app_shell.rect())
        self.ui.authentication_overlay.raise_()
        self.ui.authentication_overlay.setVisible(True)

    @Slot()
    def _on_authentification_cancelled(self) -> None:
        """Handle the authentification cancelled."""
        self.ui.authentication_overlay.hide()

    @Slot()
    def _on_authentification_confirmed(self) -> None:
        """Handle the authentification confirmation."""
        self.ui.authentication_overlay.hide()

    def forward_device_authentification_succeeded(self, device: dict) -> None:
        """Handle the device authentification succeeded."""
        signals.DEVICE.AuthentificationSucceeded.emit(device)
        self.ui.app_shell.post_toast(
            self.texts.authentification_success_toast.format(device=device["name"]),
            level="success",
        )

    def forward_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        """Handle the device selection succeeded without adding a new list entry."""
        signals.DEVICE.DeviceSelectionSucceeded.emit(
            simulation_id, device_id, device_name
        )
        self.ui.app_shell.post_toast(
            self.texts.device_selection_success_toast.format(device=device_name),
            level="success",
        )

    def forward_map_rendered(self, simulation_id: str, html_path: Path) -> None:
        """Forward map render completion to the map block."""
        signals.UI.MapRendered.emit(simulation_id, html_path)

    def forward_simulation_location_validated(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        lat: float,
        lon: float,
        label: str,
    ) -> None:
        """Forward validated simulation location to map consumers."""
        signals.SIMULATION.SimulationLocationValidated.emit(
            simulation_id,
            km,
            line_code,
            line_troncon,
            lat,
            lon,
            label,
        )

    def forward_simulation_location_rejected(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        lat: float,
        lon: float,
        reason: str,
    ) -> None:
        """Notify the user when map milestone validation fails."""
        signals.SIMULATION.SimulationLocationRejected.emit(
            simulation_id,
            km,
            line_code,
            line_troncon,
            lat,
            lon,
            reason,
        )
        self.ui.app_shell.post_toast(
            self.texts.simulation_location_rejected_toast.format(
                km=km,
                line_code=line_code,
                line_troncon=line_troncon,
                reason=reason,
            ),
            level="error",
        )

    def forward_map_render_failed(self, simulation_id: str, reason: str) -> None:
        """Forward map render failure to the map block and notify the user."""
        signals.UI.MapRenderFailed.emit(simulation_id, reason)
        self.ui.app_shell.post_toast(
            self.texts.map_render_failed_toast.format(
                simulation_id=simulation_id,
                reason=reason,
            ),
            level="error",
        )

    def forward_device_selection_failed(self, device_id: str, device_name: str) -> None:
        """Handle the device selection failed."""
        signals.DEVICE.DeviceSelectionFailed.emit(device_id, device_name)
        self.ui.app_shell.post_toast(
            self.texts.device_selection_failed_toast.format(device=device_name),
            level="error",
        )

    def forward_device_authentification_failed(
        self, ip: str, port: int, association_code: str, reason: str
    ) -> None:
        """Handle the device authentification failed."""
        signals.DEVICE.AuthentificationFailed.emit(ip, port, association_code)
        self.ui.app_shell.post_toast(
            self.texts.authentification_failed_toast.format(
                ip=ip, port=port, association_code=association_code, reason=reason
            ),
            level="error",
        )

    def forward_devices_updated(
        self, devices: list[dict], device_id_rebindings: dict[str, str] | None = None
    ) -> None:
        """Handle the devices updated."""
        rebindings = device_id_rebindings or {}
        signals.DEVICE.DevicesUpdated.emit(devices, rebindings)

    def forward_simulation_deleted(self, simulation_id: str) -> None:
        """Forward simulation deletion to map and simulation UI consumers."""
        signals.SIMULATION.SimulationDeleted.emit(simulation_id)

    def forward_remove_active_device_succeeded(self, device_id: str) -> None:
        """Handle the active device removed."""
        signals.DEVICE.RemoveActiveDeviceSucceeded.emit(device_id)
        self.ui.app_shell.post_toast(
            self.texts.active_device_removed_success_toast.format(device=device_id),
            level="success",
        )

    def forward_host_device_information_updated(
        self, name: str, os: str, ip: str
    ) -> None:
        """Handle the host device information updated."""
        signals.HOST.HostDeviceInformationUpdated.emit(name, os, ip)

    def forward_activity_log_file_updated(self, log_file_path: str) -> None:
        """Forward the app-wide activity log path to the log panel (via app signals)."""
        signals.ACTIVITY_LOG.ActivityLogFileUpdated.emit(log_file_path)

    def resizeEvent(self, event) -> None:
        """Keep authentication overlay covering the full main container."""
        super().resizeEvent(event)
        if hasattr(self, "ui") and self.ui.authentication_overlay is not None:
            self.ui.authentication_overlay.setGeometry(self.ui.app_shell.rect())
