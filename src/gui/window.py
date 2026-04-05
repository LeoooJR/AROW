"""
This file contains the main window of the application.
"""

from collections import deque
from dataclasses import dataclass
from time import monotonic
from typing import Deque, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPalette, QPixmap, QScreen
from PySide6.QtWidgets import (
    QAbstractButton,
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

import gui.ressources_rc
from gui.__init__ import __application__
from gui.colors import Theme, get_current_palette
from gui.device import DeviceItem, DevicePairingPanel, DeviceSelectionPanel
from gui.elements import (
    SVG,
    AuthentificationCard,
    ButtonGroup,
    ProgressBar,
    QuestionDialog,
    Toast,
    ToolButton,
)
from gui.event_filter import ActivityTracker
from gui.host import HostPanel
from gui.icons import ApplicationIcons, GenericIcons, OperatingSystemIcons
from gui.location import LocationPanel
from gui.logs import LogPanel
from gui.map import MapPanel
from gui.settings import Settings
from gui.signals import app_signals
from gui.stylesheet import stylesheet, stylesheet_dark, stylesheet_light
from gui.welcome import WelcomePanel
from gui.wrapper import (
    GridLayoutWrapper,
    HorizontalLayoutWrapper,
    VerticalLayoutWrapper,
)
from logger import logger


class Header(QWidget):
    """
    Header widget of the application.
    """

    @dataclass
    class UI:
        name: SVG
        light_palette_button: ToolButton
        dark_palette_button: ToolButton
        palette_button_group: ButtonGroup
        palette_button_wrapper: HorizontalLayoutWrapper
        palette_thumb: QFrame
        left_panel_visibility_request_button: ToolButton
        right_panel_visibility_request_button: ToolButton
        layout_buttons_wrapper: GridLayoutWrapper

    def __init__(self, parent=None):
        # Initialize parent QWidget
        super().__init__(parent)

        self.setObjectName("header")

        self.ui: Header.UI

        # Set fixed height from settings
        self.setFixedHeight(Settings.DIMENSION.HEADER_HEIGHT)

        # Create horizontal layout for header
        layout = QHBoxLayout()

        # Create palette button group, containing light and dark mode buttons, exclusive to one of them being selected at a time
        palette_button_group = ButtonGroup(self)
        light_palette_button = ToolButton(
            self,
            icon_path=GenericIcons.LIGHT_MODE.value,
            tooltip="Switch to light mode",
        )
        dark_palette_button = ToolButton(
            self, icon_path=GenericIcons.DARK_MODE.value, tooltip="Switch to dark mode"
        )
        palette_button_group.addButton(light_palette_button, 0)
        palette_button_group.addButton(dark_palette_button, 1)
        palette_button_group.setObjectName("palette-button-group")

        # Create palette button wrapper, containing light and dark mode buttons, horizontal layout
        palette_button_wrapper = HorizontalLayoutWrapper(
            self, widgets=[light_palette_button, dark_palette_button]
        )
        palette_button_wrapper.setObjectName("palette-button-wrapper")
        layout.addWidget(palette_button_wrapper)

        # Create palette thumb, a small frame that moves to indicate the selected palette button
        thumb_size = Settings.DIMENSION.PALETTE_THUMB_SIZE
        palette_thumb = QFrame(palette_button_wrapper)
        palette_thumb.setObjectName("palette-thumb")
        palette_thumb.setFixedSize(thumb_size, thumb_size)
        palette_thumb_layout = QHBoxLayout(palette_thumb)
        palette_thumb_layout.setContentsMargins(0, 0, 0, 0)
        palette_thumb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._palette_thumb_anim: Optional[QPropertyAnimation] = None
        QTimer.singleShot(0, self._update_palette_thumb_geometry)

        # Create name, the application name
        name = SVG(ApplicationIcons.NAME.value, self)
        name.setFixedSize(
            Settings.DIMENSION.APP_NAME_WIDTH, Settings.DIMENSION.APP_NAME_HEIGHT
        )
        # Add name to layout
        layout.addWidget(name, 1)

        # Left panels visibility button: toggles left sidebar (device + location panels). visibility=True => panels shown; at start panels are visible.
        left_panel_visibility_request_button = ToolButton(
            self,
            icon_path=GenericIcons.LAYOUT_SIDEBAR_INSET.value,
            tooltip="Toggle left panels visibility",
        )
        left_panel_visibility_request_button.setObjectName(
            "left-panel-visibility-request-button"
        )
        left_panel_visibility_request_button.setProperty("visibility", True)
        left_panel_visibility_request_button.setProperty("inset", True)

        # Right panels visibility button: toggles right sidebar (host + log panels). visibility=True => panels shown; at start panels are visible.
        right_panel_visibility_request_button = ToolButton(
            self,
            icon_path=GenericIcons.LAYOUT_SIDEBAR_INSET_REVERSE.value,
            tooltip="Toggle right panels visibility",
        )
        right_panel_visibility_request_button.setObjectName(
            "right-panel-visibility-request-button"
        )
        right_panel_visibility_request_button.setProperty("visibility", True)
        right_panel_visibility_request_button.setProperty("inset", True)

        layout_buttons_wrapper = GridLayoutWrapper(
            self,
            widgets=[
                (left_panel_visibility_request_button, 0, 0),
                (right_panel_visibility_request_button, 0, 1),
            ],
        )
        layout.addWidget(layout_buttons_wrapper)

        self.setLayout(layout)

        self.ui: Header.UI = Header.UI(
            name=name,
            light_palette_button=light_palette_button,
            dark_palette_button=dark_palette_button,
            palette_button_group=palette_button_group,
            palette_button_wrapper=palette_button_wrapper,
            palette_thumb=palette_thumb,
            left_panel_visibility_request_button=left_panel_visibility_request_button,
            right_panel_visibility_request_button=right_panel_visibility_request_button,
            layout_buttons_wrapper=layout_buttons_wrapper,
        )

        self._connect_signals()
        self._set_alignment()
        self._set_size_policy()

    def _connect_signals(self) -> None:
        """Connect signals for the header."""
        left_btn = self.ui.left_panel_visibility_request_button
        right_btn = self.ui.right_panel_visibility_request_button
        left_btn.clicked.connect(
            lambda: app_signals.LeftPanelsVisibilityRequested.emit(
                not bool(left_btn.property("visibility"))
            )
        )
        right_btn.clicked.connect(
            lambda: app_signals.RightPanelsVisibilityRequested.emit(
                not bool(right_btn.property("visibility"))
            )
        )
        self.ui.palette_button_group.buttonClicked.connect(
            self._on_palette_button_clicked
        )

    def _set_alignment(self) -> None:
        """Set the alignment of the header."""
        self.layout().setAlignment(self.ui.name, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.layout_buttons_wrapper,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.layout().setAlignment(
            self.ui.palette_button_wrapper,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )

    def _set_size_policy(self) -> None:
        """Set the size policy of the header."""
        self.ui.left_panel_visibility_request_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.right_panel_visibility_request_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.layout_buttons_wrapper.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        self.ui.light_palette_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.dark_palette_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.palette_button_wrapper.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )

    def toggle_left_panels_visibility_request_button(self) -> None:
        """Update left panels button icon and properties to the toggled state (call after body left panels visibility has been set)."""
        button = self.ui.left_panel_visibility_request_button
        if button.property("inset"):
            button.setProperty("inset", False)
            button.setProperty("visibility", False)
            button.setIcon(QIcon(GenericIcons.LAYOUT_SIDEBAR.value))
        else:
            button.setProperty("inset", True)
            button.setProperty("visibility", True)
            button.setIcon(QIcon(GenericIcons.LAYOUT_SIDEBAR_INSET.value))

    def toggle_right_panels_visibility_request_button(self) -> None:
        """Update right panels button icon and properties to the toggled state (call after body right panels visibility has been set)."""
        button = self.ui.right_panel_visibility_request_button
        if button.property("inset"):
            button.setProperty("inset", False)
            button.setProperty("visibility", False)
            button.setIcon(QIcon(GenericIcons.LAYOUT_SIDEBAR_REVERSE.value))
        else:
            button.setProperty("inset", True)
            button.setProperty("visibility", True)
            button.setIcon(QIcon(GenericIcons.LAYOUT_SIDEBAR_INSET_REVERSE.value))

    def _update_palette_thumb_geometry(self) -> None:
        """Position the palette thumb over the light button (initial or after layout)."""
        btn = self.ui.light_palette_button
        thumb = self.ui.palette_thumb
        tw, th = thumb.width(), thumb.height()
        g = btn.geometry()
        x = g.x() + (g.width() - tw) // 2
        y = g.y() + (g.height() - th) // 2
        thumb.setGeometry(QRect(x, y, tw, th))
        btn.raise_()

    def _on_palette_button_clicked(self, button: QAbstractButton) -> None:
        """Handle the palette button click."""
        if button == self.ui.light_palette_button:
            app_signals.UpdatePaletteSignal.emit("light")
        elif button == self.ui.dark_palette_button:
            app_signals.UpdatePaletteSignal.emit("dark")
        thumb = self.ui.palette_thumb
        btn_rect = button.geometry()
        tw, th = thumb.width(), thumb.height()
        target = QRect(
            btn_rect.x() + (btn_rect.width() - tw) // 2,
            btn_rect.y() + (btn_rect.height() - th) // 2,
            tw,
            th,
        )
        if (
            self._palette_thumb_anim
            and self._palette_thumb_anim.state() == QAbstractAnimation.State.Running
        ):
            self._palette_thumb_anim.stop()
        self._palette_thumb_anim = QPropertyAnimation(thumb, b"geometry")
        self._palette_thumb_anim.setStartValue(thumb.geometry())
        self._palette_thumb_anim.setEndValue(target)
        self._palette_thumb_anim.setDuration(Settings.ANIMATION.PALETTE_SWITCH_DURATION)
        self._palette_thumb_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._palette_thumb_anim.setParent(self)
        self._palette_thumb_anim.start()
        icon_size = thumb.width() - 8
        button.raise_()


class Body(QWidget):

    @dataclass
    class UI:
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
        super().__init__(parent)

        self.ui: Body.UI

        self.setObjectName("body")

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        device_selection_panel = DeviceSelectionPanel(None)
        device_selection_panel.setVisible(True)

        location_panel = LocationPanel(None)
        location_panel.setVisible(True)

        # Create left panels wrapper, a vertical layout wrapper that contains the device and location panels
        left_panels_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[device_selection_panel, location_panel],
            spacing=0,
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

        tabs.addTab(welcome_panel, "Welcome")

        tabs.setTabIcon(0, QIcon(ApplicationIcons.LOGO.value))

        map_panel = MapPanel(None)
        map_panel.setVisible(True)

        tabs.addTab(map_panel, "Map")

        tabs.setTabIcon(1, QIcon(GenericIcons.MAP.value))

        device_pairing_panel = DevicePairingPanel(None)
        device_pairing_panel.setVisible(False)

        tabs.addTab(device_pairing_panel, "Device")

        tabs.setTabIcon(2, QIcon(GenericIcons.DEVICE.value))

        progress_bar = ProgressBar(None)

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
            self, widgets=[host_panel, log_panel], spacing=0, margins=(0, 0, 0, 0)
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

        self._connect_signals()
        self._set_alignment()
        self._set_size_policy()

    def _connect_signals(self) -> None:
        """Connect body signals. Right sidebar: when one panel is reduced, expand the other. Left sidebar: same."""
        app_signals.LogPanelVisibilityRequested.connect(self._on_log_panel_toggled)
        app_signals.HostPanelVisibilityRequested.connect(self._on_host_panel_toggled)
        app_signals.DeviceSelectionPanelVisibilityRequested.connect(
            self._on_device_selection_panel_toggled
        )
        app_signals.LocationPanelVisibilityRequested.connect(
            self._on_location_panel_toggled
        )
        self.ui.tabs.currentChanged.connect(self._on_tab_changed)
        app_signals.AuthentificationSucceeded.connect(self._on_device_connected)
        app_signals.DeviceSelectionSucceeded.connect(self._on_device_connected)

    def _set_alignment(self) -> None:
        pass

    def _set_size_policy(self) -> None:
        self.ui.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:  # Map tab
            if not self.ui.map_panel.is_map_visible():  # Map not visible yet
                if self.ui.progress_bar.value() == 0:  # No phone is connected yet
                    self.ui.map_panel.helper()
                    self.ui.device_selection_panel.start_highlight_attention()
                elif self.ui.progress_bar.value() == 1:
                    pass

    def run_helper(self) -> None:
        """Run application helper animation."""
        if self.ui.progress_bar.value() == 0:
            if self.ui.tabs.currentIndex() == 1:
                self.ui.map_panel.helper()
                self.ui.device_selection_panel.start_highlight_attention()
        elif self.ui.progress_bar.value() == 1:
            pass

    def _on_log_panel_toggled(self, visible: bool) -> None:
        """Handle the log panel visibility request."""
        if not visible:
            self.set_host_panel_visibility(
                True
            )  # Show host panel when log panel is hidden, one panel must be visible at all times in UI

    def _on_host_panel_toggled(self, visible: bool) -> None:
        """Handle the host panel visibility request."""
        if not visible:
            self.set_log_panel_visibility(
                True
            )  # Show log panel when host panel is hidden, one panel must be visible at all times in UI

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

    def is_left_panels_visible(self) -> bool:
        """Check if the left panels are visible."""
        return self.ui.left_panels_wrapper.isVisible()

    def is_right_panels_visible(self) -> bool:
        """Check if the right panels are visible."""
        return self.ui.right_panels_wrapper.isVisible()

    def is_device_selection_panel_visible(self) -> bool:
        """Check if the device selection panel is visible."""
        return self.ui.device_selection_panel.is_panel_visible()

    def is_location_panel_visible(self) -> bool:
        """Check if the location panel is visible."""
        return self.ui.location_panel.is_panel_visible()

    def is_host_panel_visible(self) -> bool:
        """Check if the host panel is visible."""
        return self.ui.host_panel.is_panel_visible()

    def is_log_panel_visible(self) -> bool:
        """Check if the log panel is visible."""
        return self.ui.log_panel.is_panel_visible()

    def set_left_panels_visibility(self, visible: bool) -> None:
        """Set the left panels visibility."""
        self.ui.left_panels_wrapper.setVisible(visible)

    def set_right_panels_visibility(self, visible: bool) -> None:
        """Set the right panels visibility."""
        self.ui.right_panels_wrapper.setVisible(visible)

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

    def get_current_device(self) -> DeviceItem:
        """Get the current device."""
        return self.ui.device_selection_panel.current_device()

    def _on_device_connected(self, device: str) -> None:
        """Handle post-connection UI updates for any successful connection flow."""
        self.ui.progress_bar.setValue(1)
        self.ui.tabs.setCurrentIndex(1)
        self.ui.device_pairing_panel.setVisible(True)


class MainContainer(QWidget):

    @dataclass
    class UI:

        header: Header
        body: Body
        toast: Optional[Toast] = None

    def __init__(self, parent: QWidget = None):

        super().__init__()

        self.ui: MainContainer.UI
        self._toast_queue: Deque[tuple[str, str]] = deque()

        # Get palette from container
        # Set window color to white
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(get_current_palette().WHITE))
        self.setPalette(palette)

        # Create vertical layout for container
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create header widget
        # Header widget is the top part of the window
        header: Header = Header(self)

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

        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        """Connect main container to app signals."""
        app_signals.LeftPanelsVisibilityRequested.connect(
            self._on_left_panels_visibility_requested
        )
        app_signals.RightPanelsVisibilityRequested.connect(
            self._on_right_panels_visibility_requested
        )
        app_signals.AddDeviceRequested.connect(self._on_add_device_requested)
        app_signals.AuthentificationConfirmed.connect(
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
        logger.info("Add device request received.")
        dialog = QuestionDialog(
            self,
            title="Adding a device",
            text=f"Do you want to add a new device?",
            detailed_text=f"This action will add a new device to the list of available devices.\nMake sure the device is powered on, in developer mode and connected to the same network as the computer.\nYou must own full ownership of the device to use it with this software.",
        )
        button = dialog.exec()

        if button == QMessageBox.StandardButton.Yes:
            app_signals.AuthentificationRequested.emit()

        else:
            app_signals.AuthentificationCancelled.emit()

    def _on_authentification_confirmed(self) -> None:
        """Handle the authentification confirmation."""
        logger.info("Authentification confirmation received.")
        self.post_toast("Trying to connect to device... Please wait.", level="info")

    def post_toast(self, text: str, level: str) -> None:
        """Enqueue a toast and display messages sequentially."""
        if not text:
            return
        if not self.isVisible():
            logger.debug("Skipping toast because container is not visible.")
            return

        now = monotonic()
        last_payload = getattr(self, "_last_toast_payload", None)
        last_timestamp = getattr(self, "_last_toast_timestamp", 0.0)
        if last_payload == (text, level) and now - last_timestamp < 0.35:
            logger.debug("Skipping duplicate toast posted too quickly.")
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
                "Failed to display toast: widget was deleted during creation."
            )
            self.ui.toast = None
            QTimer.singleShot(0, self._show_next_toast)

    def _on_active_toast_destroyed(self) -> None:
        """Show the next queued toast once the active one is gone."""
        self.ui.toast = None
        QTimer.singleShot(0, self._show_next_toast)

    def wake_up(self) -> None:
        """Wake up the application."""
        self.ui.body.run_helper()


class AuthentificationOverlay(QWidget):
    """
    Authentification overlay widget.
    """

    @dataclass
    class UI:
        authentification_card: AuthentificationCard

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.setObjectName("authentification-overlay")

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch()

        authentification_card = AuthentificationCard(
            self,
            title="Authentification",
            icon_path=GenericIcons.DEVICE.value,
            description="Please enter your access credentials to continue.",
        )
        layout.addWidget(authentification_card)

        layout.addStretch()

        self.setLayout(layout)

        self.ui = AuthentificationOverlay.UI(
            authentification_card=authentification_card
        )

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

    @dataclass
    class UI:

        container: MainContainer
        authentification_overlay: AuthentificationOverlay

    def __init__(self, ui_constraints_disabled: bool = False):
        # Initialize parent QMainWindow
        super().__init__()

        self._ui_constraints_disabled = ui_constraints_disabled
        self._device_selection_dialog_open: bool = False

        self.ui: MainWindow.UI

        self.setWindowTitle(f"{__application__} - Main Window")

        # Get available screen size
        screen_size = QScreen.availableSize(QApplication.primaryScreen())

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
        self.setWindowIcon(QPixmap(ApplicationIcons.LOGO.value))

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
        if self._ui_constraints_disabled:
            app_signals.UiConstraintsDisabled.emit()
        app_signals.UpdatePaletteSignal.connect(self._on_palette_update)
        self._activity_tracker.became_idle.connect(self._on_idle)
        app_signals.AuthentificationRequested.connect(
            self._on_authentification_requested
        )
        app_signals.AuthentificationConfirmed.connect(
            self._on_authentification_confirmed
        )
        app_signals.AuthentificationCancelled.connect(
            self._on_authentification_cancelled
        )
        app_signals.DeviceSelected.connect(self._on_device_selection)

    def _on_palette_update(self, theme: Theme) -> None:
        """Handle the palette update."""
        self.setStyleSheet(stylesheet_light if theme == "light" else stylesheet_dark)
        logger.info(f"Palette updated to {theme}.")

    def _on_idle(self) -> None:
        """Handle the idle state: run helper and highlight device lists to draw attention."""
        logger.info("Idle state detected.")
        self.ui.container.wake_up()

    def _on_device_selection(self, device: DeviceItem) -> None:
        """Handle the device selection."""
        if device is None:
            return
        if self._device_selection_dialog_open:
            logger.debug(
                "Ignoring device selection while confirmation dialog is already open."
            )
            return
        self._device_selection_dialog_open = True
        logger.info(f"Device selection requested: {device.get_text()}.")
        dialog = QuestionDialog(
            self,
            title="Connecting to device",
            text=f"Do you want to connect to {device.get_text()} device?",
            detailed_text=f"This action will connect to the {device.get_text()} device.\nMake sure the device is powered on, in developer mode and connected to the same network as the computer.\nYou must own full ownership of the device to use it with this software.",
        )
        try:
            button = dialog.exec()

            if button == QMessageBox.StandardButton.Yes:
                if self._ui_constraints_disabled:
                    logger.warning(
                        "UI constraints disabled, skipping device connection request."
                    )
                    self.on_device_selection_succeeded(device.get_text())
                app_signals.DeviceConnectionRequested.emit(device.get_text())
            else:
                app_signals.DeviceConnectionCancelled.emit()
        finally:
            self._device_selection_dialog_open = False

    def _on_authentification_requested(self) -> None:
        """Handle the authentification request."""
        self.ui.authentification_overlay.setGeometry(self.ui.container.rect())
        self.ui.authentification_overlay.raise_()
        self.ui.authentification_overlay.setVisible(True)

    def _on_authentification_cancelled(self) -> None:
        """Handle the authentification cancelled."""
        logger.info("Authentification cancelled.")
        self.ui.authentification_overlay.hide()

    def _on_authentification_confirmed(self) -> None:
        """Handle the authentification confirmation."""
        logger.info("Authentification confirmed.")
        self.ui.authentification_overlay.hide()
        if self._ui_constraints_disabled:
            self.on_device_pairing_succeeded("Samsung Galaxy")

    def on_device_pairing_succeeded(self, device: str) -> None:
        """Handle the device pairing succeeded."""
        logger.info(f"Device pairing succeeded: {device}.")
        app_signals.AuthentificationSucceeded.emit(device)
        self.ui.container.post_toast(
            f"Successfully connected to device: {device}.", level="success"
        )

    def on_device_selection_succeeded(self, device: str) -> None:
        """Handle the device selection succeeded without adding a new list entry."""
        logger.info(f"Device selection succeeded: {device}.")
        app_signals.DeviceSelectionSucceeded.emit(device)
        self.ui.container.post_toast(
            f"Successfully connected to device: {device}.", level="success"
        )

    def on_device_pairing_failed(
        self, ip: str, port: int, association_code: str
    ) -> None:
        """Handle the device pairing failed."""
        logger.warning(
            f"Device pairing failed: {ip}:{port} with association code: {association_code}."
        )
        app_signals.AuthentificationFailed.emit(ip, port, association_code)
        self.ui.container.post_toast(
            f"Failed to connect to device: {ip}:{port} with association code: {association_code}.",
            level="error",
        )

    def on_devices_updated(self, devices: list[str]) -> None:
        """Handle the devices updated."""
        logger.info(f"Devices updated: {devices}.")
        app_signals.DevicesUpdated.emit(devices)

    def on_host_device_information_updated(self, name: str, os: str, ip: str) -> None:
        """Handle the host device information updated."""
        logger.info(f"Host device information updated: {name} {os} {ip}.")
        app_signals.HostDeviceInformationUpdated.emit(name, os, ip)

    def resizeEvent(self, event) -> None:
        """Keep authentication overlay covering the full main container."""
        super().resizeEvent(event)
        if hasattr(self, "ui") and self.ui.authentification_overlay is not None:
            self.ui.authentification_overlay.setGeometry(self.ui.container.rect())
