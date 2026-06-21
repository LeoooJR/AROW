"""Map-related GUI blocks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    QUrl,
    Slot,
)
from PySide6.QtGui import QFont
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.application_paths import get_or_create_application_dir
from gui.blocks.map.device_required_placeholder import DeviceRequiredMapPlaceholder
from gui.blocks.map.map_loading_placeholder import MapLoadingPlaceholder
from gui.blocks.map.map_render_failed_placeholder import MapRenderFailedPlaceholder
from gui.blocks.map.map_settings import map_settings
from gui.colors import Theme
from gui.components import SVG, LeadingIconLabel, ToolButton
from gui.components.buttons.button_settings import button_settings
from gui.components.media import get_svg_size
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import GridLayoutWrapper, HorizontalLayoutWrapper
from logger import logger

_INVALIDATE_LEAFLET_MAPS_JS = """
(function () {
  if (typeof L === "undefined") {
    return;
  }
  for (var key in window) {
    try {
      var value = window[key];
      if (value && value.invalidateSize && value._container) {
        value.invalidateSize(true);
      }
    } catch (error) {}
  }
})();
"""


class Canvas(QWebEngineView):
    """Map canvas: web engine view."""

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the map canvas."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the map canvas."""

        pass

    def __init__(self, parent: QWidget = None):
        """Create the web engine view used to render the map.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = Canvas.Text()
        self.ui = Canvas.UI()

        self.setObjectName("map-canvas")
        self.setMinimumSize(map_settings.CANVAS_SIZE, map_settings.CANVAS_SIZE)

        web_settings = self.settings()
        web_settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        web_settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        web_settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        self.loadFinished.connect(self._on_load_finished)
        self._leaflet_page_ready: bool = False

        self._finalize_ui_hooks()

    def load(self, url: QUrl) -> None:
        """Reset Leaflet readiness before loading a new page."""
        self._leaflet_page_ready = False
        super().load(url)

    def _invalidate_leaflet_size(self) -> None:
        """Ask Leaflet to recalculate map dimensions for the current canvas size."""
        self.page().runJavaScript(_INVALIDATE_LEAFLET_MAPS_JS)

    @Slot(bool)
    def _on_load_finished(self, ok: bool) -> None:
        """Refresh Leaflet map layout after local HTML loads in the canvas."""
        if not ok:
            self._leaflet_page_ready = False
            return
        self._leaflet_page_ready = True
        self._invalidate_leaflet_size()

    def resizeEvent(self, event) -> None:
        """Re-sync Leaflet map dimensions when the canvas is resized after load."""
        super().resizeEvent(event)
        if self._leaflet_page_ready:
            self._invalidate_leaflet_size()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the canvas."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the canvas."""
        pass

    def _set_size_policy(self) -> None:
        """Centralize size policies for the canvas."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _connect_signals(self) -> None:
        """Connect signals for the canvas."""
        pass


class Legend(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Legend labels for real, simulated, and kilometric map cues."""

        location_label: Final[str] = "Real position"
        simulated_location_label: Final[str] = "Simulated position"
        kilometric_point_label: Final[str] = "Kilometric point"

    @dataclass
    class UI:
        """Icon+label rows composing the map legend."""

        location_label_icon: LeadingIconLabel
        simulated_location_label_icon: LeadingIconLabel
        legend_first_row: HorizontalLayoutWrapper
        kilometric_point_label_icon: LeadingIconLabel
        legend_second_row: HorizontalLayoutWrapper

    def __init__(self, parent: QWidget = None):
        """Lay out legend rows for map symbology.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.texts = Legend.Text()

        self.setObjectName("map-legend")
        self.setProperty("main-section-divider-bottom", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            map_settings.LEGEND_PADDING_LEFT,
            map_settings.LEGEND_PADDING_TOP,
            map_settings.LEGEND_PADDING_RIGHT,
            map_settings.LEGEND_PADDING_BOTTOM,
        )
        layout.setSpacing(map_settings.LEGEND_SPACING)  # Spacing between legend items

        location_label_icon = LeadingIconLabel(
            None,
            icon=GenericIcons.LOCATION,
            text=self.texts.location_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        simulated_location_label_icon = LeadingIconLabel(
            None,
            icon=GenericIcons.FAKE_LOCATION,
            text=self.texts.simulated_location_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        legend_first_row = HorizontalLayoutWrapper(
            self,
            widgets=[location_label_icon, simulated_location_label_icon],
            spacing=Settings.SPACING.LG,
            margins=Settings.SPACING.MARGIN_SMALL,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        kilometric_point_label_icon = LeadingIconLabel(
            None,
            icon=GenericIcons.MILESTONE,
            text=self.texts.kilometric_point_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        legend_second_row = HorizontalLayoutWrapper(
            self,
            widgets=[kilometric_point_label_icon],
            spacing=Settings.SPACING.LG,
            margins=Settings.SPACING.MARGIN_SMALL,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        layout.addWidget(legend_first_row)
        layout.addWidget(legend_second_row)

        self.setLayout(layout)

        self.ui = Legend.UI(
            location_label_icon=location_label_icon,
            simulated_location_label_icon=simulated_location_label_icon,
            legend_first_row=legend_first_row,
            kilometric_point_label_icon=kilometric_point_label_icon,
            legend_second_row=legend_second_row,
        )
        self._set_alignment()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh legend row icons for the active theme."""
        self.ui.location_label_icon.apply_theme_icons(theme)
        self.ui.simulated_location_label_icon.apply_theme_icons(theme)
        self.ui.kilometric_point_label_icon.apply_theme_icons(theme)

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the legend and its UI widgets."""
        self.ui.legend_first_row.get_layout().setAlignment(
            self.ui.location_label_icon,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
        )
        self.ui.legend_first_row.get_layout().setAlignment(
            self.ui.simulated_location_label_icon,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
        )
        self.ui.legend_second_row.get_layout().setAlignment(
            self.ui.kilometric_point_label_icon,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter,
        )


class Location(QWidget):

    @dataclass(frozen=True)
    class Text:
        """Coordinate field labels and control tooltips."""

        latitude_label: Final[str] = "Latitude"
        longitude_label: Final[str] = "Longitude"
        crosshair_button_tooltip: Final[str] = "Center map on current location"

    @dataclass
    class UI:
        """Latitude/longitude stacks and recenter control."""

        latitude_widget: QWidget
        latitude_label: QLabel
        longitude_widget: QWidget
        longitude_label: QLabel
        crosshair_button: ToolButton

    def __init__(self, parent: QWidget | None = None, icon_path: str | None = None):
        """Build a coordinate readout row with optional leading icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon_path: Asset path shown beside the coordinate stack.
        """
        super().__init__(parent)

        self.texts = Location.Text()

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(
            map_settings.COORDINATE_SPACING
        )  # Spacing between SVG and coordinate widgets

        latitude_widget = QWidget(self)
        latitude_widget.setObjectName("location-latitude-widget")
        latitude_widget.setMinimumWidth(map_settings.COORDINATE_WIDGET_MIN_WIDTH)
        latitude_widget.setMaximumHeight(map_settings.COORDINATE_WIDGET_MAX_HEIGHT)
        latitude_widget.setLayout(QVBoxLayout())
        latitude_widget.layout().setContentsMargins(
            map_settings.COORDINATE_WIDGET_PADDING_LEFT,
            map_settings.COORDINATE_WIDGET_PADDING_TOP,
            map_settings.COORDINATE_WIDGET_PADDING_RIGHT,
            map_settings.COORDINATE_WIDGET_PADDING_BOTTOM,
        )
        latitude_widget.layout().setSpacing(map_settings.COORDINATE_WIDGET_SPACING)

        latitude_label = QLabel(self.texts.latitude_label)
        latitude_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_SMALL, QFont.Weight.Normal)
        )

        self._coordinate_lead_svg: SVG | None = None
        if icon_path is not None:
            self._coordinate_lead_svg = SVG(icon_path, self)
            svg_size = get_svg_size(Settings.FONT.SIZE_DEFAULT)
            self._coordinate_lead_svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._coordinate_lead_svg.setFixedSize(svg_size)
            layout.addWidget(self._coordinate_lead_svg)

        latitude_widget.layout().addWidget(latitude_label)

        longitude_widget = QWidget(self)
        longitude_widget.setObjectName("location-longitude-widget")
        longitude_widget.setMinimumWidth(map_settings.COORDINATE_WIDGET_MIN_WIDTH)
        longitude_widget.setMaximumHeight(map_settings.COORDINATE_WIDGET_MAX_HEIGHT)
        longitude_widget.setLayout(QVBoxLayout())
        longitude_widget.layout().setContentsMargins(
            map_settings.COORDINATE_WIDGET_PADDING_LEFT,
            map_settings.COORDINATE_WIDGET_PADDING_TOP,
            map_settings.COORDINATE_WIDGET_PADDING_RIGHT,
            map_settings.COORDINATE_WIDGET_PADDING_BOTTOM,
        )
        longitude_widget.layout().setSpacing(map_settings.COORDINATE_WIDGET_SPACING)

        longitude_label = QLabel(self.texts.longitude_label)
        longitude_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_SMALL, QFont.Weight.Normal)
        )
        longitude_widget.layout().addWidget(longitude_label)

        layout.addWidget(latitude_widget)
        layout.addWidget(longitude_widget)

        crosshair_button = ToolButton(
            parent=self,
            icon=GenericIcons.CROSSHAIR,
            tooltip=self.texts.crosshair_button_tooltip,
        )
        crosshair_button.setEnabled(False)
        layout.addWidget(crosshair_button)

        self.setLayout(layout)

        self.ui = Location.UI(
            latitude_widget=latitude_widget,
            latitude_label=latitude_label,
            longitude_widget=longitude_widget,
            longitude_label=longitude_label,
            crosshair_button=crosshair_button,
        )
        self._finalize_ui_hooks()

    def apply_row_icons(self, theme: Theme, lead: GenericIcons) -> None:
        """Update the coordinate row leading marker and crosshair for ``theme``."""
        if self._coordinate_lead_svg is not None:
            self._coordinate_lead_svg.set_path(icon_qt_path_for_theme(theme, lead))
        self.ui.crosshair_button.apply_theme_icons(theme)

    @property
    def crosshair_button(self) -> ToolButton:
        """Return the coordinate row recenter button."""
        return self.ui.crosshair_button

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the location widget."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the location widget."""
        pass

    def _set_size_policy(self) -> None:
        """Centralize size policies for the location widget."""
        pass

    def _set_alignment(self) -> None:
        """Centralize layout and widget alignment for the location widget."""
        self.ui.latitude_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.latitude_widget.layout().setAlignment(
            self.ui.latitude_label,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        self.ui.longitude_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.longitude_widget.layout().setAlignment(
            self.ui.longitude_label,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        self.layout().setAlignment(
            self.ui.latitude_widget, Qt.AlignmentFlag.AlignVCenter
        )
        self.layout().setAlignment(
            self.ui.longitude_widget, Qt.AlignmentFlag.AlignVCenter
        )
        self.layout().setAlignment(
            self.ui.crosshair_button, Qt.AlignmentFlag.AlignCenter
        )

    def set_latitude(self, latitude: float):
        """Append a latitude value label inside the latitude stack.

        Args:
            latitude: Latitude value to display as text.
        """
        logger.info(f"Setting latitude to {latitude}.")
        self.ui.latitude_widget.layout().addWidget(QLabel(str(latitude)))

    def set_longitude(self, longitude: float):
        """Append a longitude value label inside the longitude stack.

        Args:
            longitude: Longitude value to display as text.
        """
        logger.info(f"Setting longitude to {longitude}.")
        self.ui.longitude_widget.layout().addWidget(QLabel(str(longitude)))

    def clear_latitude(self):
        """Clear latitude values from this location row placeholder."""
        pass

    def clear_longitude(self):
        """Clear longitude values from this location row placeholder."""
        pass


class Coordinates(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Simulation state labels and transport control tooltips."""

        simulation_state_off: Final[str] = "Simulation inactive"
        simulation_state_on: Final[str] = "Simulation active"
        play_button_tooltip: Final[str] = "Start simulation"
        pause_button_tooltip: Final[str] = "Pause simulation"

    @dataclass
    class UI:
        """Simulation toggle visuals, coordinate rows, and play control."""

        simulation_state_container: QWidget
        simulation_state_off: LeadingIconLabel
        simulation_state_on: LeadingIconLabel
        location_widget: Location
        simulated_location_widget: Location
        play_button: ToolButton

    def __init__(self, parent: QWidget = None):
        """Build the coordinates bar with simulation state and play/pause control.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.texts = Coordinates.Text()

        self.setObjectName("map-coordinates")
        self.setProperty("main-section-divider", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            map_settings.LEGEND_PADDING_LEFT,
            map_settings.LEGEND_PADDING_TOP,
            map_settings.LEGEND_PADDING_RIGHT,
            map_settings.LEGEND_PADDING_BOTTOM,
        )
        layout.setSpacing(
            map_settings.COORDINATES_SPACING
        )  # Spacing between location widgets

        simulation_state_off = LeadingIconLabel(
            self,
            icon=GenericIcons.OFF,
            text=self.texts.simulation_state_off,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        simulation_state_on = LeadingIconLabel(
            self,
            icon=GenericIcons.ON,
            text=self.texts.simulation_state_on,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )

        opacity_off = QGraphicsOpacityEffect(self)
        opacity_off.setOpacity(1.0)
        simulation_state_off.setGraphicsEffect(opacity_off)
        opacity_on = QGraphicsOpacityEffect(self)
        opacity_on.setOpacity(0.0)
        simulation_state_on.setGraphicsEffect(opacity_on)

        simulation_state_container = GridLayoutWrapper(self)
        simulation_state_container.add_widget(simulation_state_off, 0, 0)
        simulation_state_container.add_widget(simulation_state_on, 0, 0)
        layout.addWidget(simulation_state_container)

        play_button = ToolButton(
            parent=self,
            icon=GenericIcons.PLAY,
            tooltip=self.texts.play_button_tooltip,
            icon_size=button_settings.TOOLBUTTON_PROMINENT_ICON_SIZE,
        )
        play_button.setEnabled(True)
        play_button.setProperty("toggle", False)
        play_button.setProperty("simulation-control", True)
        play_button.clicked.connect(self._on_play_button_clicked)
        layout.addWidget(play_button)

        location_widget = Location(self, icon_qt_path(GenericIcons.LOCATION))
        layout.addWidget(location_widget)

        simulated_location_widget = Location(
            self, icon_qt_path(GenericIcons.FAKE_LOCATION)
        )
        layout.addWidget(simulated_location_widget)

        self.setLayout(layout)

        self._state_animation_group: QParallelAnimationGroup | None = None
        self.ui = Coordinates.UI(
            simulation_state_container=simulation_state_container,
            simulation_state_off=simulation_state_off,
            simulation_state_on=simulation_state_on,
            location_widget=location_widget,
            simulated_location_widget=simulated_location_widget,
            play_button=play_button,
        )
        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh coordinate controls and row icons for the active theme."""
        self.ui.simulation_state_off.apply_theme_icons(theme)
        self.ui.simulation_state_on.apply_theme_icons(theme)
        pb = self.ui.play_button
        pb.set_icon(GenericIcons.PAUSE if pb.property("toggle") else GenericIcons.PLAY)
        pb.apply_theme_icons(theme)
        self.ui.location_widget.apply_row_icons(theme, GenericIcons.LOCATION)
        self.ui.simulated_location_widget.apply_row_icons(
            theme, GenericIcons.FAKE_LOCATION
        )

    @property
    def play_button(self) -> ToolButton:
        """Return the simulation play/pause button."""
        return self.ui.play_button

    @property
    def location_widget(self) -> Location:
        """Return the real-location coordinate widget."""
        return self.ui.location_widget

    @property
    def simulated_location_widget(self) -> Location:
        """Return the simulated-location coordinate widget."""
        return self.ui.simulated_location_widget

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the coordinates section."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the coordinates section."""
        pass

    def _set_size_policy(self) -> None:
        """Centralize size policies for the coordinates section."""
        pass

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the coordinates section."""
        self.layout().setAlignment(
            self.ui.simulation_state_container, Qt.AlignmentFlag.AlignCenter
        )
        self.layout().setAlignment(self.ui.play_button, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.location_widget, Qt.AlignmentFlag.AlignCenter
        )
        self.layout().setAlignment(
            self.ui.simulated_location_widget, Qt.AlignmentFlag.AlignCenter
        )

    def set_simulation_state(self, state: bool) -> None:
        """Animate and reflect active vs inactive simulation in the UI.

        Args:
            state: True when simulation is active (show on-state, pause affordance).
        """
        duration = map_settings.SIMULATION_STATE_TRANSITION_DURATION
        easing = QEasingCurve.Type.OutCubic

        effect_off = self.ui.simulation_state_off.graphicsEffect()
        effect_on = self.ui.simulation_state_on.graphicsEffect()

        if state:
            self.ui.play_button.set_icon(GenericIcons.PAUSE)
            self.ui.play_button.setToolTip(self.texts.pause_button_tooltip)
            anim_off = QPropertyAnimation(effect_off, b"opacity")
            anim_off.setDuration(duration)
            anim_off.setStartValue(1.0)
            anim_off.setEndValue(0.0)
            anim_off.setEasingCurve(easing)
            anim_on = QPropertyAnimation(effect_on, b"opacity")
            anim_on.setDuration(duration)
            anim_on.setStartValue(0.0)
            anim_on.setEndValue(1.0)
            anim_on.setEasingCurve(easing)
        else:
            self.ui.play_button.set_icon(GenericIcons.PLAY)
            self.ui.play_button.setToolTip(self.texts.play_button_tooltip)
            anim_off = QPropertyAnimation(effect_off, b"opacity")
            anim_off.setDuration(duration)
            anim_off.setStartValue(0.0)
            anim_off.setEndValue(1.0)
            anim_off.setEasingCurve(easing)
            anim_on = QPropertyAnimation(effect_on, b"opacity")
            anim_on.setDuration(duration)
            anim_on.setStartValue(1.0)
            anim_on.setEndValue(0.0)
            anim_on.setEasingCurve(easing)

        self.ui.play_button.setEnabled(True)
        if (
            self._state_animation_group is not None
            and self._state_animation_group.state() == QAbstractAnimation.State.Running
        ):
            self._state_animation_group.stop()
        self._state_animation_group = QParallelAnimationGroup(self)
        self._state_animation_group.addAnimation(anim_off)
        self._state_animation_group.addAnimation(anim_on)
        self._state_animation_group.start()

    @Slot()
    def _on_play_button_clicked(self) -> None:
        """Handle the play button click."""
        if self.ui.play_button.property("toggle"):
            logger.info("Simulation paused.")
            self.ui.play_button.setProperty("toggle", False)
            self.set_simulation_state(False)
        else:
            logger.info("Simulation started.")
            self.ui.play_button.setProperty("toggle", True)
            self.set_simulation_state(True)


class MapBlock(QWidget):
    """Map view: canvas/placeholder (expandable) and coordinates bar."""

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the map block."""

        pass

    @dataclass
    class UI:
        """Canvas, coordinates strip, and empty-state placeholder."""

        legend: Legend
        canvas: Canvas
        coordinates: Coordinates
        placeholder: QStackedWidget
        device_required_placeholder: DeviceRequiredMapPlaceholder
        map_loading_placeholder: MapLoadingPlaceholder
        map_render_failed_placeholder: MapRenderFailedPlaceholder

    def __init__(self, parent=None):
        """Lay out placeholder, hidden canvas, and coordinates bar.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.texts = MapBlock.Text()

        layout = QVBoxLayout()
        layout.setContentsMargins(
            *Settings.SPACING.MARGIN_NONE
        )  # Padding handled by parent
        layout.setSpacing(
            map_settings.MAP_SPACING
        )  # Consistent spacing between canvas and coordinates

        legend = Legend(self)
        layout.addWidget(legend)
        legend.setVisible(False)

        canvas = Canvas(self)
        layout.addWidget(canvas, 1)
        canvas.setMinimumSize(
            map_settings.MIN_WIDTH_LARGE, map_settings.MIN_HEIGHT_SMALL
        )
        canvas.setVisible(False)

        placeholder = QStackedWidget(self)
        placeholder.setObjectName("map-placeholder")
        placeholder.setMinimumSize(
            map_settings.MIN_WIDTH_LARGE,
            map_settings.MIN_HEIGHT_SMALL,
        )

        device_required_placeholder = DeviceRequiredMapPlaceholder(placeholder)
        map_loading_placeholder = MapLoadingPlaceholder(placeholder)
        map_render_failed_placeholder = MapRenderFailedPlaceholder(placeholder)
        placeholder.addWidget(device_required_placeholder)
        placeholder.addWidget(map_loading_placeholder)
        placeholder.addWidget(map_render_failed_placeholder)
        layout.addWidget(placeholder, 1)

        coordinates = Coordinates(self)
        layout.addWidget(coordinates)

        self.setLayout(layout)

        self.ui = MapBlock.UI(
            legend=legend,
            canvas=canvas,
            coordinates=coordinates,
            placeholder=placeholder,
            device_required_placeholder=device_required_placeholder,
            map_loading_placeholder=map_loading_placeholder,
            map_render_failed_placeholder=map_render_failed_placeholder,
        )
        self._placeholder_helper_anim: QSequentialAnimationGroup | None = None
        self._pending_render_simulation_id: str | None = None

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the map view."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the map view."""
        self.layout().setAlignment(self.ui.coordinates, Qt.AlignmentFlag.AlignCenter)

    def _set_size_policy(self) -> None:
        """Centralize size policies for the map view and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.coordinates.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the map view and its UI widgets."""
        signals.UI.RunHelperAnimationRequested.connect(self._on_run_helper_animation)
        signals.UI.MapTabActivated.connect(self._on_run_helper_animation)
        signals.DEVICE.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        signals.DEVICE.AuthentificationFailed.connect(self._on_authentification_failed)
        signals.DEVICE.DeviceSelectionFailed.connect(self._on_device_selection_failed)
        signals.DEVICE.RemoveActiveDeviceSucceeded.connect(
            self._on_remove_active_device_succeeded
        )
        signals.UI.MapRendered.connect(self._on_map_rendered)
        signals.UI.MapRenderFailed.connect(self._on_map_render_failed)

    def is_canvas_visible(self) -> bool:
        """Return whether the concrete map canvas is currently visible."""
        return self.ui.canvas.isVisible()

    @property
    def legend(self) -> Legend:
        """Return the map legend widget."""
        return self.ui.legend

    @property
    def canvas(self) -> Canvas:
        """Return the map canvas widget."""
        return self.ui.canvas

    @property
    def coordinates(self) -> Coordinates:
        """Return the map coordinates widget."""
        return self.ui.coordinates

    @property
    def placeholder(self) -> QStackedWidget:
        """Return the map placeholder widget."""
        return self.ui.placeholder

    def show_device_required_placeholder(self) -> None:
        """Show the placeholder that asks the user to open the device list."""
        self.ui.placeholder.setCurrentWidget(self.ui.device_required_placeholder)

    def show_map_loading_placeholder(self) -> None:
        """Show the placeholder used while the map is being generated."""
        self.ui.placeholder.setCurrentWidget(self.ui.map_loading_placeholder)
        self.ui.placeholder.setVisible(True)
        self.ui.canvas.setVisible(False)

    def show_map_render_failed_placeholder(self) -> None:
        """Show the placeholder used when map generation fails."""
        self.ui.placeholder.setCurrentWidget(self.ui.map_render_failed_placeholder)
        self.ui.placeholder.setVisible(True)
        self.ui.canvas.setVisible(False)

    def show_map_canvas(self) -> None:
        """Hide placeholders and show the rendered map canvas."""
        self.ui.placeholder.setVisible(False)
        self.ui.canvas.setVisible(True)
        self.ui.canvas.updateGeometry()
        layout = self.layout()
        if layout is not None:
            layout.activate()

    def _map_html_path(self, simulation_id: str) -> Path:
        """Return the expected on-disk HTML path for a simulation map."""
        return (
            get_or_create_application_dir()
            / "simulations"
            / simulation_id
            / "map"
            / f"{simulation_id}.html"
        )

    def _load_map_html(self, simulation_id: str) -> None:
        """Load the rendered map HTML into the canvas when available."""
        self._load_map_html_from_path(simulation_id, self._map_html_path(simulation_id))

    def _load_map_html_from_path(self, simulation_id: str, html_path: Path) -> None:
        """Load map HTML from a concrete on-disk path into the canvas."""
        if not html_path.is_file():
            logger.warning(
                "MapBlock: rendered map HTML not found",
                simulation_id=simulation_id,
                path=str(html_path),
            )
            return
        load_url = QUrl.fromLocalFile(str(html_path.resolve()))
        self.show_map_canvas()

        def _load_after_layout() -> None:
            self.ui.canvas.load(load_url)
            logger.info(
                "MapBlock: map HTML loaded into canvas",
                simulation_id=simulation_id,
                path=str(html_path),
            )

        QTimer.singleShot(0, _load_after_layout)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh theme-dependent icons for all map block children."""
        self.ui.legend.apply_theme_icons(theme)
        self.ui.device_required_placeholder.apply_theme_icons(theme)
        self.ui.map_loading_placeholder.apply_theme_icons(theme)
        self.ui.map_render_failed_placeholder.apply_theme_icons(theme)
        self.ui.coordinates.apply_theme_icons(theme)

    ### Slots ###

    @Slot(str, str, str)
    def _on_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        """Update placeholder after auth or device selection succeeds."""
        self._pending_render_simulation_id = simulation_id
        self.show_map_loading_placeholder()
        self._on_run_helper_animation()
        signals.UI.RenderMapRequested.emit(simulation_id)

    def _is_stale_render_update(self, simulation_id: str) -> bool:
        """Return True when an async render completion no longer matches active state."""
        return self._pending_render_simulation_id != simulation_id

    @Slot(str, object)
    def _on_map_rendered(self, simulation_id: str, html_path: Path) -> None:
        """Load the map canvas after async rendering completes."""
        if self._is_stale_render_update(simulation_id):
            logger.debug(
                "MapBlock: ignoring stale map render completion",
                simulation_id=simulation_id,
                pending_simulation_id=self._pending_render_simulation_id,
            )
            return
        self._pending_render_simulation_id = None
        self._load_map_html_from_path(simulation_id, html_path)

    @Slot(str, str)
    def _on_map_render_failed(self, simulation_id: str, reason: str) -> None:
        """Show the render-failure placeholder when map generation fails."""
        if self._is_stale_render_update(simulation_id):
            logger.debug(
                "MapBlock: ignoring stale map render failure",
                simulation_id=simulation_id,
                pending_simulation_id=self._pending_render_simulation_id,
                reason=reason,
            )
            return
        self._pending_render_simulation_id = None
        logger.warning(
            "MapBlock: map render failed",
            simulation_id=simulation_id,
            reason=reason,
        )
        self.show_map_render_failed_placeholder()
        self._on_run_helper_animation()

    @Slot(str, str)
    def _on_device_selection_failed(self, device_id: str, device_name: str) -> None:
        """Pulse placeholder when device selection fails."""
        self._on_run_helper_animation()

    @Slot()
    def _on_authentification_failed(self, *_args) -> None:
        """Pulse placeholder when authentification fails."""
        self._on_run_helper_animation()

    @Slot(str)
    def _on_remove_active_device_succeeded(self, device_id: str) -> None:
        """Reset placeholder when the active device is removed."""
        self._pending_render_simulation_id = None
        self.show_device_required_placeholder()
        self.ui.placeholder.setVisible(True)
        self.ui.canvas.setVisible(False)
        self._on_run_helper_animation()

    @Slot()
    def _on_run_helper_animation(self) -> None:
        """Run the placeholder helper animation."""
        if not self.ui.placeholder.isVisible():
            return  # Placeholder is not visible, no need to animate
        self._play_placeholder_helper_animation()

    def _play_placeholder_helper_animation(self) -> None:
        """
        Run a one-shot opacity pulse on the canvas placeholder. Help to draw attention of the user to the placeholder.
        """
        current = cast(
            DeviceRequiredMapPlaceholder
            | MapLoadingPlaceholder
            | MapRenderFailedPlaceholder,
            self.ui.placeholder.currentWidget(),
        )
        self._placeholder_helper_anim = current.play_helper_animation(
            self._placeholder_helper_anim
        )


Map = MapBlock
