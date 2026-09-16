"""Main application workspace layout and page routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from gui.animation import animate_widget_visibility
from gui.components import ProgressBar
from gui.constants.colors import Theme
from gui.constants.icons import GenericIcons
from gui.constants.settings import Settings
from gui.pages import DevicePage, MapPage, WelcomePage
from gui.panels import DeviceSelectionPanel, LogPanel
from gui.routing import PageRoute, PageRouter
from gui.signals import signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper

PRE_SIMULATION_PROGRESS_STEP_LABELS: Final[list[str]] = [
    "Not started",
    "Device selected",
    "Location set",
    "Ready to start",
]


class WorkspaceLayout(QWidget):
    """Compose side panels around the routed central application pages."""

    @dataclass(frozen=True)
    class Text:
        welcome_route: Final[str] = "Welcome"
        map_route: Final[str] = "Map"
        device_route: Final[str] = "Device"

    @dataclass
    class UI:
        device_selection_panel: DeviceSelectionPanel
        welcome_page: WelcomePage
        map_page: MapPage
        device_page: DevicePage
        log_panel: LogPanel
        router: PageRouter
        progress_bar: ProgressBar
        router_wrapper: VerticalLayoutWrapper
        left_panels_wrapper: VerticalLayoutWrapper
        right_panels_wrapper: VerticalLayoutWrapper

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the routed workspace and its collapsible side panels.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = WorkspaceLayout.Text()
        self._left_panels_visible = True
        self._right_panels_visible = True
        self.setObjectName("body")

        layout = QHBoxLayout()
        layout.setContentsMargins(*(Settings.SPACING.SM,) * 4)
        layout.setSpacing(Settings.SPACING.SM)

        device_selection_panel = DeviceSelectionPanel()
        device_selection_panel.setVisible(True)
        left_panels_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[device_selection_panel],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        left_panels_wrapper.setObjectName("left-panels-wrapper")
        left_panels_wrapper.setVisible(True)
        layout.addWidget(left_panels_wrapper)

        router = PageRouter()
        router.setObjectName("tabs")
        router.setProperty("tab", True)
        router.setTabPosition(PageRouter.TabPosition.North)
        router.setMovable(False)

        welcome_page = WelcomePage()
        map_page = MapPage()
        device_page = DevicePage()
        router.register(
            PageRoute.WELCOME,
            welcome_page,
            title=self.texts.welcome_route,
            icon=GenericIcons.HAND_RAISED,
        )
        router.register(
            PageRoute.MAP,
            map_page,
            title=self.texts.map_route,
            icon=GenericIcons.MAP,
        )
        router.register(
            PageRoute.DEVICE,
            device_page,
            title=self.texts.device_route,
            icon=GenericIcons.DEVICE,
            visible=False,
        )

        progress_bar = ProgressBar(
            None,
            minimum=0,
            maximum=3,
            value=0,
            orientation=Qt.Orientation.Horizontal,
            step_labels=PRE_SIMULATION_PROGRESS_STEP_LABELS,
        )
        router_wrapper = VerticalLayoutWrapper(self, widgets=[router, progress_bar])
        # Preserve selectors and object names used by the existing stylesheet.
        router_wrapper.setObjectName("tabs-wrapper")
        router_wrapper.setProperty("panel", True)
        layout.addWidget(router_wrapper, 1)

        log_panel = LogPanel()
        log_panel.setVisible(True)
        right_panels_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[log_panel],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        right_panels_wrapper.setObjectName("right-panels-wrapper")
        right_panels_wrapper.setVisible(True)
        layout.addWidget(right_panels_wrapper)
        self.setLayout(layout)

        self.ui = WorkspaceLayout.UI(
            device_selection_panel=device_selection_panel,
            welcome_page=welcome_page,
            map_page=map_page,
            device_page=device_page,
            log_panel=log_panel,
            router=router,
            progress_bar=progress_bar,
            router_wrapper=router_wrapper,
            left_panels_wrapper=left_panels_wrapper,
            right_panels_wrapper=right_panels_wrapper,
        )
        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        self.ui.router.route_changed.connect(self._on_route_changed)
        signals.DEVICE.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        signals.DEVICE.RemoveActiveDeviceSucceeded.connect(
            self._on_remove_active_device_succeeded
        )
        signals.UI.TargetSelectionRequested.connect(self._on_target_selection_requested)
        signals.SIMULATION.SimulationLocationValidated.connect(
            self._on_simulation_location_validated
        )
        self.ui.router.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.log_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    @Slot(object)
    def _on_route_changed(self, route: PageRoute) -> None:
        if route is PageRoute.MAP:
            signals.UI.MapTabActivated.emit()

    @Slot()
    def _on_target_selection_requested(self) -> None:
        if self.ui.router.current_route is not PageRoute.MAP:
            self.ui.router.navigate(PageRoute.MAP)

    def set_left_panels_visibility(self, visible: bool) -> None:
        """Animate the left panel group to the requested visibility."""
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
        """Animate the right panel group to the requested visibility."""
        self._right_panels_visible = visible
        animate_widget_visibility(
            self.ui.right_panels_wrapper,
            visible=visible,
            axis="horizontal",
            hide_widget_when_collapsed=True,
        )
        if visible:
            signals.UI.ShortenDeviceSelectionPanelRequested.emit()
        else:
            signals.UI.ExtendDeviceSelectionPanelRequested.emit()
        self._sync_welcome_workspace_mode_later(
            left_visible=self._left_panels_visible,
            right_visible=visible,
        )
        self._refresh_log_panel_layout_later()

    def _refresh_log_panel_layout_later(self) -> None:
        self.ui.log_panel.refresh_layout()
        QTimer.singleShot(
            Settings.ANIMATION.PANEL_VISIBILITY_DURATION + Settings.SPACING.SM,
            self.ui.log_panel.refresh_layout,
        )

    def _sync_welcome_workspace_mode_later(
        self, *, left_visible: bool, right_visible: bool
    ) -> None:
        enabled = not left_visible and not right_visible
        delay_ms = Settings.ANIMATION.PANEL_VISIBILITY_DURATION + Settings.SPACING.SM
        if enabled:
            self._set_welcome_workspace_mode(True)
            QTimer.singleShot(delay_ms, self._enable_welcome_workspace_mode_deferred)
            return
        QTimer.singleShot(delay_ms, self._disable_welcome_workspace_mode_deferred)

    @Slot()
    def _enable_welcome_workspace_mode_deferred(self) -> None:
        self._set_welcome_workspace_mode(True)

    @Slot()
    def _disable_welcome_workspace_mode_deferred(self) -> None:
        self._set_welcome_workspace_mode(False)

    def _set_welcome_workspace_mode(self, enabled: bool) -> None:
        self.ui.welcome_page.set_expanded_workspace_mode(enabled)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh workspace child icons for the active theme."""
        self.ui.router.apply_theme_icons(theme)
        for page in (self.ui.map_page, self.ui.device_page):
            page.apply_theme_icons(theme)
        self.ui.welcome_page.apply_theme_icons(theme)
        self.ui.device_selection_panel.apply_theme_icons(theme)
        self.ui.log_panel.apply_theme_icons(theme)

    @Slot(str, str, str)
    def _on_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        self.ui.progress_bar.setValue(1)
        self.ui.router.navigate(PageRoute.MAP)

    @Slot(str)
    def _on_remove_active_device_succeeded(self, device_id: str) -> None:
        self.ui.progress_bar.setValue(0)
        self.ui.router.navigate(PageRoute.WELCOME)

    @Slot(str, int, str, int, float, float, str)
    def _on_simulation_location_validated(
        self,
        simulation_id: str,
        km: int,
        line_code: str,
        line_troncon: int,
        lat: float,
        lon: float,
        label: str,
    ) -> None:
        self.ui.progress_bar.setValue(2)
