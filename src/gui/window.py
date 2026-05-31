"""
This file contains the main window of the application.
"""

import os
from collections import deque
from dataclasses import dataclass, field
from time import monotonic
from typing import Deque, Final, Optional

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QPixmap, QScreen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

import gui.faker as ui_faker
import gui.ressources_rc
from gui.__init__ import __application__
from gui.animation import animate_widget_visibility
from gui.blocks.device import DeviceItem
from gui.blocks.top_bar import TopBar
from gui.colors import Theme, get_current_palette, set_current_theme
from gui.components import (
    AuthentificationCard,
    ProgressBar,
    QuestionDialog,
    Toast,
)
from gui.device_panel import DevicePairingPanel, DeviceSelectionPanel
from gui.event_filter import ActivityTracker
from gui.host_panel import HostPanel
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
    icons_need_theme_updates,
)
from gui.location_panel import LocationPanel
from gui.log_panel import LogPanel
from gui.map import MapPanel
from gui.settings import Settings
from gui.signals import view_signals
from gui.stylesheet import stylesheet, stylesheet_dark, stylesheet_light
from gui.welcome import WelcomePanel
from gui.wrapper import (
    HorizontalLayoutWrapper,
    VerticalLayoutWrapper,
)
from logger import logger

PRE_SIMULATION_PROGRESS_STEP_LABELS: Final[list[str]] = [
    "Not started",
    "Device selected",
    "Location set",
    "Ready to start",
]

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
            "MainWindow: invalid offscreen screen size, using fallback",
            env_var=_OFFSCREEN_SCREEN_SIZE_ENV,
            raw=raw,
        )
        return QSize(_DEFAULT_OFFSCREEN_SCREEN_SIZE)
    if (
        width < Settings.DIMENSION.WINDOW_MIN_WIDTH
        or height < Settings.DIMENSION.WINDOW_MIN_HEIGHT
    ):
        logger.warning(
            "MainWindow: offscreen screen size below minimum, using fallback",
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


class Body(QWidget):

    TAB_MAP = 1

    @dataclass(frozen=True)
    class Text:
        """Text used in element across the body."""

        welcome_tab: Final[str] = "Welcome"
        map_tab: Final[str] = "Map"
        device_tab: Final[str] = "Device"

    @dataclass
    class UI:
        """UI elements used in the body widgets."""

        device_selection_panel: DeviceSelectionPanel
        location_panel: LocationPanel
        map_panel: MapPanel
        device_pairing_panel: DevicePairingPanel
        host_panel: HostPanel
        log_panel: LogPanel
        tabs: QTabWidget
        progress_bar: ProgressBar
        tabs_wrapper: HorizontalLayoutWrapper
        left_panels_wrapper: VerticalLayoutWrapper
        right_panels_wrapper: VerticalLayoutWrapper

    def __init__(self, parent=None):
        """Initialize the body widget.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: Body.UI
        self.texts = Body.Text()
        self._left_panels_visible = True
        self._right_panels_visible = True

        self.setObjectName("body")

        layout = QHBoxLayout()
        layout.setContentsMargins(
            Settings.SPACING.SM,
            Settings.SPACING.SM,
            Settings.SPACING.SM,
            Settings.SPACING.SM,
        )
        layout.setSpacing(Settings.SPACING.SM)

        device_selection_panel = DeviceSelectionPanel(None)
        device_selection_panel.setVisible(True)

        location_panel = LocationPanel(None)
        location_panel.setVisible(True)

        # Create left panels wrapper, a vertical layout wrapper that contains the device and location panels
        left_panels_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[device_selection_panel, location_panel],
            spacing=Settings.SPACING.SM,
            margins=(0, 0, 0, 0),
        )
        left_panels_wrapper.setObjectName("left-panels-wrapper")
        # Visibility are True by default, but set it explicitly to ensure the panels are visible at application start
        left_panels_wrapper.setVisible(True)
        layout.addWidget(left_panels_wrapper)

        tabs = QTabWidget(None)

        tabs.setObjectName("tabs")

        tabs.setProperty("tab", True)

        tabs.setTabPosition(QTabWidget.TabPosition.North)

        tabs.setMovable(False)

        welcome_panel = WelcomePanel(None)
        welcome_panel.setVisible(True)

        tabs.addTab(welcome_panel, self.texts.welcome_tab)

        tabs.setTabIcon(0, QIcon(icon_qt_path(GenericIcons.HAND_RAISED)))

        map_panel = MapPanel(None)
        map_panel.setVisible(True)

        tabs.addTab(map_panel, self.texts.map_tab)

        tabs.setTabIcon(1, QIcon(icon_qt_path(GenericIcons.MAP)))

        device_pairing_panel = DevicePairingPanel(None)

        tabs.addTab(device_pairing_panel, self.texts.device_tab)

        tabs.setTabIcon(2, QIcon(icon_qt_path(GenericIcons.DEVICE)))

        tabs.setTabVisible(2, False)

        progress_bar = ProgressBar(
            None,
            minimum=0,
            maximum=3,
            value=0,
            orientation=Qt.Orientation.Horizontal,
            step_labels=PRE_SIMULATION_PROGRESS_STEP_LABELS,
        )

        tabs_wrapper = VerticalLayoutWrapper(self, widgets=[tabs, progress_bar])

        tabs_wrapper.setObjectName("tabs-wrapper")

        tabs_wrapper.setProperty("panel", True)

        layout.addWidget(tabs_wrapper, 1)

        host_panel = HostPanel(None)
        # Visibility are True by default, but set it explicitly to ensure the panel is visible at application start
        host_panel.setVisible(True)

        log_panel = LogPanel(None)
        # Visibility are True by default, but set it explicitly to ensure the panel is visible at application start
        log_panel.setVisible(True)

        # Create right panels wrapper, a vertical layout wrapper that contains the host and log panels
        right_panels_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[host_panel, log_panel],
            spacing=Settings.SPACING.SM,
            margins=(0, 0, 0, 0),
        )
        right_panels_wrapper.setObjectName("right-panels-wrapper")
        # Visibility are True by default, but set it explicitly to ensure the panels are visible at application start
        right_panels_wrapper.setVisible(True)
        layout.addWidget(right_panels_wrapper)

        self.setLayout(layout)

        self.ui: Body.UI = Body.UI(
            device_selection_panel=device_selection_panel,
            location_panel=location_panel,
            map_panel=map_panel,
            device_pairing_panel=device_pairing_panel,
            host_panel=host_panel,
            log_panel=log_panel,
            tabs=tabs,
            progress_bar=progress_bar,
            left_panels_wrapper=left_panels_wrapper,
            right_panels_wrapper=right_panels_wrapper,
            tabs_wrapper=tabs_wrapper,
        )

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the body."""
        self._connect_signals()
        self._set_alignment()
        self._set_size_policy()

    def _connect_signals(self) -> None:
        """Connect body signals. Right sidebar: when one panel is reduced, expand the other. Left sidebar: same."""

        #### Signals for handling the panel visibility requests ####
        view_signals.LogPanelVisibilityRequested.connect(self._on_log_panel_toggled)
        view_signals.HostPanelVisibilityRequested.connect(self._on_host_panel_toggled)
        view_signals.DeviceSelectionPanelVisibilityRequested.connect(
            self._on_device_selection_panel_toggled
        )
        view_signals.LocationPanelVisibilityRequested.connect(
            self._on_location_panel_toggled
        )

        #### Signals for handling the tab changes ####
        self.ui.tabs.currentChanged.connect(self._on_tab_changed)

        #### Signals for handling the step transition from authentification to map display ####
        view_signals.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        view_signals.ActiveDeviceRemoved.connect(self._on_active_device_removed)

        view_signals.TargetSelectionRequested.connect(
            self._on_target_selection_requested
        )

    def _set_alignment(self) -> None:
        pass

    def _set_size_policy(self) -> None:
        self.ui.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.host_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.log_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _on_tab_changed(self, index: int) -> None:
        if index != self.TAB_MAP:
            return
        view_signals.MapTabActivated.emit()

    def _on_log_panel_toggled(self, visible: bool) -> None:
        """Handle the log panel visibility request."""
        if not visible:
            self.set_host_panel_visibility(
                True
            )  # Show host panel when log panel is hidden, one panel must be visible at all times in UI
            self.ui.host_panel.extend_panel()
        else:
            self.ui.host_panel.shorten_panel()
        self._refresh_log_panel_layout_later()

    def _on_host_panel_toggled(self, visible: bool) -> None:
        """Handle the host panel visibility request."""
        if not visible:
            self.set_log_panel_visibility(
                True
            )  # Show log panel when host panel is hidden, one panel must be visible at all times in UI
        self._refresh_log_panel_layout_later()

    def _on_device_selection_panel_toggled(self, visible: bool) -> None:
        """Handle the device panel visibility request."""
        if not visible:
            self.set_location_panel_visibility(
                True
            )  # Show location panel when device panel is hidden, one panel must be visible at all times in UI

    def _on_location_panel_toggled(self, visible: bool) -> None:
        """Handle the location panel visibility request."""
        if not visible:
            self.set_device_selection_panel_visibility(
                True
            )  # Show device panel when location panel is hidden, one panel must be visible at all times in UI

    def _on_target_selection_requested(self) -> None:
        """Route the location panel CTA to the existing map selection surface."""
        if self.ui.tabs.currentIndex() != self.TAB_MAP:
            self.ui.tabs.setCurrentIndex(self.TAB_MAP)

    def set_left_panels_visibility(self, visible: bool) -> None:
        """Set the left panels visibility."""
        self._left_panels_visible = visible
        animate_widget_visibility(
            self.ui.left_panels_wrapper,
            visible=visible,
            axis="horizontal",
            hide_widget_when_collapsed=True,
        )
        self._sync_welcome_workspace_mode_later(
            left_visible=visible,
            right_visible=self._right_panels_visible,
        )
        self._refresh_log_panel_layout_later()

    def set_right_panels_visibility(self, visible: bool) -> None:
        """Set the right panels visibility."""
        self._right_panels_visible = visible
        animate_widget_visibility(
            self.ui.right_panels_wrapper,
            visible=visible,
            axis="horizontal",
            hide_widget_when_collapsed=True,
        )
        if not visible:
            view_signals.ExtendDeviceSelectionPanelRequested.emit()
        else:
            view_signals.ShortenDeviceSelectionPanelRequested.emit()
        self._sync_welcome_workspace_mode_later(
            left_visible=self._left_panels_visible,
            right_visible=visible,
        )
        self._refresh_log_panel_layout_later()

    def set_device_selection_panel_visibility(self, visible: bool) -> None:
        """Set the device selection panel visibility."""
        if visible:
            self.ui.device_selection_panel.show_panel()
        else:
            self.ui.device_selection_panel.hide_panel()

    def set_log_panel_visibility(self, visible: bool) -> None:
        """Set the log panel visibility."""
        if visible:
            self.ui.log_panel.show_panel()
        else:
            self.ui.log_panel.hide_panel()
        self._refresh_log_panel_layout_later()

    def set_location_panel_visibility(self, visible: bool) -> None:
        """Set the location panel visibility."""
        if visible:
            self.ui.location_panel.show_panel()
        else:
            self.ui.location_panel.hide_panel()

    def set_host_panel_visibility(self, visible: bool) -> None:
        """Set the host panel visibility."""
        if visible:
            self.ui.host_panel.show_panel()
        else:
            self.ui.host_panel.hide_panel()
        self._refresh_log_panel_layout_later()

    def _refresh_log_panel_layout_later(self) -> None:
        """Refresh activity rows after sidebar visibility animations update geometry."""
        self.ui.log_panel.refresh_layout()
        QTimer.singleShot(
            Settings.ANIMATION.PANEL_VISIBILITY_DURATION + Settings.SPACING.SM,
            self.ui.log_panel.refresh_layout,
        )

    def _sync_welcome_workspace_mode_later(
        self, *, left_visible: bool, right_visible: bool
    ) -> None:
        """Update welcome-only wide layout after sidebar visibility changes."""
        enabled = not left_visible and not right_visible
        delay_ms = Settings.ANIMATION.PANEL_VISIBILITY_DURATION + Settings.SPACING.SM
        if enabled:
            self._set_welcome_workspace_mode(True)
            QTimer.singleShot(delay_ms, lambda: self._set_welcome_workspace_mode(True))
            return
        QTimer.singleShot(delay_ms, lambda: self._set_welcome_workspace_mode(False))

    def _set_welcome_workspace_mode(self, enabled: bool) -> None:
        welcome = self.ui.tabs.widget(0)
        if welcome is not None and hasattr(welcome, "set_expanded_workspace_mode"):
            welcome.set_expanded_workspace_mode(enabled)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Re-resolve tab and side-panel icon resources for ``theme``."""
        tabs = self.ui.tabs
        tabs.setTabIcon(
            0, QIcon(icon_qt_path_for_theme(theme, GenericIcons.HAND_RAISED))
        )
        tabs.setTabIcon(1, QIcon(icon_qt_path_for_theme(theme, GenericIcons.MAP)))
        tabs.setTabIcon(2, QIcon(icon_qt_path_for_theme(theme, GenericIcons.DEVICE)))
        welcome = tabs.widget(0)
        if welcome is not None and hasattr(welcome, "apply_theme_icons"):
            welcome.apply_theme_icons(theme)
        self.ui.map_panel.apply_theme_icons(theme)
        self.ui.device_pairing_panel.apply_theme_icons(theme)
        self.ui.device_selection_panel.apply_theme_icons(theme)
        self.ui.location_panel.apply_theme_icons(theme)
        self.ui.host_panel.apply_theme_icons(theme)
        self.ui.log_panel.apply_theme_icons(theme)

    def _on_device_selection_succeeded(self, device: str) -> None:
        """Handle post-connection UI updates for any successful connection flow."""
        self.ui.progress_bar.setValue(1)
        self.ui.tabs.setCurrentIndex(1)
        self.ui.tabs.setTabVisible(2, True)

    def _on_active_device_removed(self) -> None:
        """Handle the active device removed."""
        logger.info("Body: active device removed")
        self.ui.progress_bar.setValue(0)
        self.ui.tabs.setCurrentIndex(0)
        self.ui.tabs.setTabVisible(2, False)


class MainContainer(QWidget):

    @dataclass(frozen=True)
    class Text:
        """User-visible strings for dialogs and toasts in the main container."""

        add_device_dialog_title: Final[str] = "Adding a device"
        add_device_dialog_text: Final[str] = "Do you want to add a new device?"
        add_device_dialog_detailed_text: Final[str] = (
            "This action will add a new device to the list of available devices.\n"
            "Make sure the device is powered on, in developer mode and connected to the same network as the computer.\n"
            "You must own full ownership of the device to use it with this software."
        )
        connecting_to_device_toast: Final[str] = (
            "Trying to connect to device... Please wait."
        )

    @dataclass
    class UI:
        """Composed widgets for the main shell (header, body, optional toast)."""

        header: TopBar
        body: Body
        toast: Optional[Toast] = None

    def __init__(self, parent: QWidget = None):
        """Build the main vertical layout with header and body.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """

        super().__init__()

        self.ui: MainContainer.UI
        self.texts = MainContainer.Text()
        self._toast_queue: Deque[tuple[str, str]] = deque()

        # Get palette from container
        # Set window color to white
        palette = self.palette()
        palette.setColor(
            QPalette.ColorRole.Window, QColor(get_current_palette().CANVAS)
        )
        self.setPalette(palette)

        # Create vertical layout for container
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create header widget
        # Header widget is the top part of the window
        header: TopBar = TopBar(self)

        # Add header to layout
        layout.addWidget(header)

        # Create body widget
        # Body widget is the middle part of the window, containing panels
        body: Body = Body(self)

        # Add body to layout, 1 means it will take remaining space
        layout.addWidget(body, 1)  # Add stretch factor to make it take remaining space

        # Set layout to container
        self.setLayout(layout)

        self.ui = MainContainer.UI(header=header, body=body)

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh icon-bearing subtrees (palette background handled in MainWindow)."""
        self.ui.header.apply_theme_icons(theme)
        self.ui.body.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the main container."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        """Connect main container to app signals."""
        view_signals.LeftPanelsVisibilityRequested.connect(
            self._on_left_panels_visibility_requested
        )
        view_signals.RightPanelsVisibilityRequested.connect(
            self._on_right_panels_visibility_requested
        )
        view_signals.AddDeviceRequested.connect(self._on_add_device_requested)
        view_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )

    def _on_left_panels_visibility_requested(self, visible: bool) -> None:
        """Apply new left panels visibility to body and sync header button state."""
        self.ui.body.set_left_panels_visibility(visible)
        self.ui.header.toggle_left_panels_visibility_request_button()

    def _on_right_panels_visibility_requested(self, visible: bool) -> None:
        """Apply new right panels visibility to body and sync header button state."""
        self.ui.body.set_right_panels_visibility(visible)
        self.ui.header.toggle_right_panels_visibility_request_button()

    def _on_add_device_requested(self) -> None:
        """Handle the add device request."""
        logger.info("MainContainer: add device requested")
        dialog = QuestionDialog(
            self,
            title=self.texts.add_device_dialog_title,
            text=self.texts.add_device_dialog_text,
            detailed_text=self.texts.add_device_dialog_detailed_text,
        )
        button = dialog.exec()

        if button == QMessageBox.StandardButton.Yes:
            view_signals.AuthentificationRequested.emit()

        else:
            view_signals.AuthentificationCancelled.emit()

    def _on_authentification_confirmed(self) -> None:
        """Handle the authentification confirmation."""
        logger.info("MainContainer: authentification confirmation received")
        self.post_toast(self.texts.connecting_to_device_toast, level="info")

    def post_toast(self, text: str, level: str) -> None:
        """Enqueue a toast and display messages sequentially."""
        if not text:
            return
        if not self.isVisible():
            logger.debug(
                "MainContainer: toast skipped (container not visible)",
            )
            return

        now = monotonic()
        last_payload = getattr(self, "_last_toast_payload", None)
        last_timestamp = getattr(self, "_last_toast_timestamp", 0.0)
        if last_payload == (text, level) and now - last_timestamp < 0.35:
            logger.debug(
                "MainContainer: toast skipped (duplicate within debounce window)",
            )
            return
        self._last_toast_payload = (text, level)
        self._last_toast_timestamp = now

        self._toast_queue.append((text, level))
        self._show_next_toast()

    def _show_next_toast(self) -> None:
        """Show next toast only when no active toast is visible."""
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
                "MainContainer: toast display failed (widget deleted during creation)",
            )
            self.ui.toast = None
            QTimer.singleShot(0, self._show_next_toast)

    def _on_active_toast_destroyed(self) -> None:
        """Show the next queued toast once the active one is gone."""
        self.ui.toast = None
        QTimer.singleShot(0, self._show_next_toast)


class AuthentificationOverlay(QWidget):
    """
    Authentification overlay widget.
    """

    @dataclass(frozen=True)
    class Text:
        """Copy for the authentification overlay (title and supporting description)."""

        title: Final[str] = "Authentification"
        description: Final[str] = "Please enter your access credentials to continue."

    @dataclass
    class UI:
        """Widgets shown on the authentification overlay."""

        authentification_card: AuthentificationCard

    def __init__(self, parent: QWidget = None):
        """Lay out the centered authentification card over the main content.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.texts = AuthentificationOverlay.Text()

        self.setObjectName("authentification-overlay")

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch()

        authentification_card = AuthentificationCard(
            self,
            title=self.texts.title,
            icon_path=icon_qt_path(GenericIcons.DEVICE),
            description=self.texts.description,
        )
        layout.addWidget(authentification_card)

        layout.addStretch()

        self.setLayout(layout)

        self.ui = AuthentificationOverlay.UI(
            authentification_card=authentification_card
        )

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        card = self.ui.authentification_card
        card.apply_theme_icons(theme)

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the authentification overlay."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _set_alignment(self) -> None:
        self.layout().setAlignment(
            self.ui.authentification_card, Qt.AlignmentFlag.AlignCenter
        )

    def _connect_signals(self) -> None:
        pass


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
        demo_device_id: Final[str] = "1234567890"
        demo_device_name: Final[str] = field(
            default_factory=ui_faker.generate_android_device_model
        )
        demo_device_os: Final[str] = field(
            default_factory=ui_faker.generate_android_release_label
        )
        demo_device_location: Final[str] = field(
            default_factory=ui_faker.generate_city_state_location
        )
        demo_device_last_communication: Final[str] = "2026-01-01 12:00:00"
        authentification_success_toast: str = (
            "Successfully connected to device: {device}."
        )
        authentification_failed_toast: str = (
            "Failed to authentificate device: {ip}:{port} with association code: {association_code}: {reason}."
        )
        device_selection_failed_toast: str = "Failed to select device: {device}."
        device_selection_success_toast: str = "Successfully selected device: {device}."

    @dataclass
    class UI:
        """Root widgets: main content container and optional authentification layer."""

        container: MainContainer
        authentification_overlay: AuthentificationOverlay

    def __init__(self, ui_constraints_disabled: bool = False):
        """Create the main window, layout, and signal wiring.

        Args:
            ui_constraints_disabled: When True, skip UI sizing constraints used in tests or special modes.
        """
        # Initialize parent QMainWindow
        super().__init__()

        self._ui_constraints_disabled = ui_constraints_disabled
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
        container = MainContainer(self)
        self.setObjectName("main-container")

        # Set window icon to logo
        self.setWindowIcon(QPixmap(icon_qt_path(ApplicationIcons.LOGO)))

        # Set the main container as the central widget to fill the window
        self.setCentralWidget(container)

        # Create authentication overlay above the main container.
        # Parented to container so it covers only app content area and blocks interaction underneath.
        authentification_overlay = AuthentificationOverlay(container)
        authentification_overlay.setGeometry(container.rect())
        authentification_overlay.raise_()
        authentification_overlay.setVisible(False)

        self.ui = MainWindow.UI(
            container=container, authentification_overlay=authentification_overlay
        )

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the main window."""

        #### Debugging signals ####
        if self._ui_constraints_disabled:
            view_signals.UiConstraintsDisabled.emit()

        #### Signals for handling the palette update ####
        view_signals.UpdatePaletteSignal.connect(self._on_palette_update)

        #### Signals for handling the idle state ####
        self._activity_tracker.became_idle.connect(self._on_idle)

        #### Signals for handling the authentification workflow ####
        view_signals.AuthentificationRequested.connect(
            self._on_authentification_requested
        )
        view_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        view_signals.AuthentificationCancelled.connect(
            self._on_authentification_cancelled
        )

        #### Signals for handling the device selection workflow ####
        view_signals.DeviceSelectionRequested.connect(
            self._on_device_selection_requested
        )

    def _on_palette_update(self, theme: Theme) -> None:
        """Handle the palette update."""
        set_current_theme(theme)
        self.setStyleSheet(stylesheet_light if theme == "light" else stylesheet_dark)
        palette = self.ui.container.palette()
        palette.setColor(
            QPalette.ColorRole.Window, QColor(get_current_palette().CANVAS)
        )
        self.ui.container.setPalette(palette)
        self._refresh_theme_icons(theme)
        logger.info("MainWindow: palette updated", theme=str(theme))

    def _refresh_theme_icons(self, theme: Theme) -> None:
        """Repaint pixmap/icon widgets when assets differ per theme."""
        if not icons_need_theme_updates():
            return
        self.setWindowIcon(
            QPixmap(icon_qt_path_for_theme(theme, ApplicationIcons.LOGO))
        )
        self.ui.container.apply_theme_icons(theme)
        self.ui.authentification_overlay.apply_theme_icons(theme)

    def _on_idle(self) -> None:
        """Handle the idle state: run helper and highlight device lists to draw attention."""
        logger.info("MainWindow: idle state detected")
        # self.ui.container.wake_up()
        view_signals.RunHelperAnimationRequested.emit()

    def forward_adb_server_started(self) -> None:
        """Forward the ADB server started signal."""
        view_signals.ADBServerStarted.emit()

    def forward_adb_server_stopped(self) -> None:
        """Forward the ADB server stopped signal."""
        view_signals.ADBServerStopped.emit()

    def _on_device_selection_requested(self, device_id: str, device_name: str) -> None:
        """Handle the device selection request."""
        if device_id is None:
            return
        if self._device_selection_dialog_open:
            logger.debug(
                "MainWindow: device selection ignored (dialog already open)",
            )
            return
        self._device_selection_dialog_open = True
        logger.info(
            "MainWindow: device selection requested",
            device_id=device_id,
        )
        dialog = QuestionDialog(
            self,
            title=self.texts.connect_device_dialog_title,
            text=self.texts.connect_device_dialog_text.format(device=device_name),
            detailed_text=self.texts.connect_device_dialog_detailed_text.format(
                device=device_name
            ),
        )
        try:
            button = dialog.exec()

            if button == QMessageBox.StandardButton.Yes:
                if self._ui_constraints_disabled:
                    logger.warning(
                        "MainWindow: device selection request skipped (UI constraints disabled)",
                    )
                    self.forward_device_selection_succeeded(
                        {
                            "id": device_id,
                            "name": device_name,
                            "os": self.texts.demo_device_os,
                            "location": self.texts.demo_device_location,
                            "last_communication": self.texts.demo_device_last_communication,
                        }
                    )
                else:
                    view_signals.DeviceSelectionConfirmed.emit(device_id, device_name)
            else:
                view_signals.DeviceSelectionCancelled.emit()
        finally:
            self._device_selection_dialog_open = False

    def _on_authentification_requested(self) -> None:
        """Handle the authentification request."""
        self.ui.authentification_overlay.setGeometry(self.ui.container.rect())
        self.ui.authentification_overlay.raise_()
        self.ui.authentification_overlay.setVisible(True)

    def _on_authentification_cancelled(self) -> None:
        """Handle the authentification cancelled."""
        logger.info("MainWindow: authentification cancelled")
        self.ui.authentification_overlay.hide()

    def _on_authentification_confirmed(self) -> None:
        """Handle the authentification confirmation."""
        logger.info("MainWindow: authentification confirmed")
        self.ui.authentification_overlay.hide()
        if self._ui_constraints_disabled:
            self.forward_device_authentification_succeeded(
                {
                    "id": self.texts.demo_device_id,
                    "name": self.texts.demo_device_name,
                    "os": self.texts.demo_device_os,
                    "location": self.texts.demo_device_location,
                    "last_communication": self.texts.demo_device_last_communication,
                }
            )

    def forward_device_authentification_succeeded(self, device: dict) -> None:
        """Handle the device authentification succeeded."""
        logger.info(
            "MainWindow: device authentification succeeded", device=device["name"]
        )
        view_signals.AuthentificationSucceeded.emit(device)
        self.ui.container.post_toast(
            self.texts.authentification_success_toast.format(device=device["name"]),
            level="success",
        )

    def forward_device_selection_succeeded(
        self, device_id: str, device_name: str
    ) -> None:
        """Handle the device selection succeeded without adding a new list entry."""
        logger.info("MainWindow: device selection succeeded", device=device_name)
        view_signals.DeviceSelectionSucceeded.emit(device_id, device_name)
        self.ui.container.post_toast(
            self.texts.device_selection_success_toast.format(device=device_name),
            level="success",
        )

    def forward_device_selection_failed(self, device_id: str, device_name: str) -> None:
        """Handle the device selection failed."""
        logger.warning("MainWindow: device selection failed", device=device_name)
        view_signals.DeviceSelectionFailed.emit(device_id, device_name)
        self.ui.container.post_toast(
            self.texts.device_selection_failed_toast.format(device=device_name),
            level="error",
        )

    def forward_device_authentification_failed(
        self, ip: str, port: int, association_code: str, reason: str
    ) -> None:
        """Handle the device authentification failed."""
        logger.warning(
            "MainWindow: device authentification failed",
            ip=ip,
            port=port,
            association_code=association_code,
            reason=reason,
        )
        view_signals.AuthentificationFailed.emit(ip, port, association_code)
        self.ui.container.post_toast(
            self.texts.authentification_failed_toast.format(
                ip=ip, port=port, association_code=association_code, reason=reason
            ),
            level="error",
        )

    def forward_devices_updated(self, devices: list[dict]) -> None:
        """Handle the devices updated."""
        logger.info(
            "MainWindow: devices updated",
            device_count=len(devices),
            device_descriptors=devices,
        )
        view_signals.DevicesUpdated.emit(devices)

    def forward_active_device_removed(self) -> None:
        """Handle the active device removed."""
        logger.info("MainWindow: active device removed")
        view_signals.ActiveDeviceRemoved.emit()

    def forward_host_device_information_updated(
        self, name: str, os: str, ip: str
    ) -> None:
        """Handle the host device information updated."""
        logger.info(
            "MainWindow: host device information updated",
            name=name,
            host_os=os,
            ip=ip,
        )
        view_signals.HostDeviceInformationUpdated.emit(name, os, ip)

    def forward_activity_log_file_updated(self, log_file_path: str) -> None:
        """Forward the app-wide activity log path to the log panel (via app signals)."""
        logger.info(
            "MainWindow: activity log file path updated",
            log_file_path=log_file_path,
        )
        view_signals.ActivityLogFileUpdated.emit(log_file_path)

    def resizeEvent(self, event) -> None:
        """Keep authentication overlay covering the full main container."""
        super().resizeEvent(event)
        if hasattr(self, "ui") and self.ui.authentification_overlay is not None:
            self.ui.authentification_overlay.setGeometry(self.ui.container.rect())
