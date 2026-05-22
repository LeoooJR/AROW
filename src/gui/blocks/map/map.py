"""Map-related GUI blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
)
from PySide6.QtGui import QFont
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import SVG, LeadingIconLabel, PlaceHolder, ToolButton
from gui.components.media import get_svg_size
from gui.icons import GenericIcons, icon_qt_path, icon_qt_path_for_theme
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import GridLayoutWrapper, HorizontalLayoutWrapper
from logger import logger


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
        self.setMinimumSize(
            Settings.DIMENSION.CANVAS_SIZE, Settings.DIMENSION.CANVAS_SIZE
        )

        self._finalize_ui_hooks()

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

        self.ui: Legend.UI
        self.texts = Legend.Text()

        self.setObjectName("map-legend")
        self.setProperty("main-section-divider-bottom", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.MAP.LEGEND_PADDING_LEFT,
            Settings.MAP.LEGEND_PADDING_TOP,
            Settings.MAP.LEGEND_PADDING_RIGHT,
            Settings.MAP.LEGEND_PADDING_BOTTOM,
        )
        layout.setSpacing(Settings.MAP.LEGEND_SPACING)  # Spacing between legend items

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

        self.ui: Legend.UI = Legend.UI(
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

    def __init__(self, parent: QWidget = None, icon_path: str = None):
        """Build a coordinate readout row with optional leading icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon_path: Asset path shown beside the coordinate stack.
        """
        super().__init__(parent)

        self.ui: Location.UI
        self.texts = Location.Text()

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        layout.setSpacing(
            Settings.LOCATION.COORDINATE_SPACING
        )  # Spacing between SVG and coordinate widgets

        latitude_widget = QWidget(self)
        latitude_widget.setObjectName("location-latitude-widget")
        latitude_widget.setMinimumWidth(Settings.LOCATION.WIDGET_MIN_WIDTH)
        latitude_widget.setMaximumHeight(Settings.LOCATION.WIDGET_MAX_HEIGHT)
        latitude_widget.setLayout(QVBoxLayout())
        latitude_widget.layout().setContentsMargins(
            Settings.LOCATION.WIDGET_PADDING_LEFT,
            Settings.LOCATION.WIDGET_PADDING_TOP,
            Settings.LOCATION.WIDGET_PADDING_RIGHT,
            Settings.LOCATION.WIDGET_PADDING_BOTTOM,
        )
        latitude_widget.layout().setSpacing(Settings.LOCATION.WIDGET_SPACING)

        latitude_label = QLabel(self.texts.latitude_label)
        latitude_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_SMALL, QFont.Weight.Normal)
        )
        latitude_label_font_size = latitude_label.font().pointSize()

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
        longitude_widget.setMinimumWidth(Settings.LOCATION.WIDGET_MIN_WIDTH)
        longitude_widget.setMaximumHeight(Settings.LOCATION.WIDGET_MAX_HEIGHT)
        longitude_widget.setLayout(QVBoxLayout())
        longitude_widget.layout().setContentsMargins(
            Settings.LOCATION.WIDGET_PADDING_LEFT,
            Settings.LOCATION.WIDGET_PADDING_TOP,
            Settings.LOCATION.WIDGET_PADDING_RIGHT,
            Settings.LOCATION.WIDGET_PADDING_BOTTOM,
        )
        longitude_widget.layout().setSpacing(Settings.LOCATION.WIDGET_SPACING)

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

        self.ui: Location.UI = Location.UI(
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

        self.ui: Coordinates.UI
        self.texts = Coordinates.Text()

        self.setObjectName("map-coordinates")
        self.setProperty("main-section-divider", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.MAP.LEGEND_PADDING_LEFT,
            Settings.MAP.LEGEND_PADDING_TOP,
            Settings.MAP.LEGEND_PADDING_RIGHT,
            Settings.MAP.LEGEND_PADDING_BOTTOM,
        )
        layout.setSpacing(
            Settings.MAP.COORDINATES_SPACING
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
            icon_size=Settings.DIMENSION.TOOLBUTTON_PROMINENT_ICON_SIZE,
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
        self.ui: Coordinates.UI = Coordinates.UI(
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
        duration = Settings.ANIMATION.SIMULATION_STATE_TRANSITION_DURATION
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
        """Placeholder copy when the map cannot load yet."""

        placeholder: Final[str] = "Select a device to get started..."
        loading_placeholder: Final[str] = "Map is being loaded..."

    @dataclass
    class UI:
        """Canvas, coordinates strip, and empty-state placeholder."""

        legend: Legend
        canvas: Canvas
        coordinates: Coordinates
        placeholder: PlaceHolder

    def __init__(self, parent=None):
        """Lay out placeholder, hidden canvas, and coordinates bar.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: MapBlock.UI
        self.texts = MapBlock.Text()

        layout = QVBoxLayout()
        layout.setContentsMargins(
            *Settings.SPACING.MARGIN_NONE
        )  # Padding handled by parent
        layout.setSpacing(
            Settings.MAP.MAP_SPACING
        )  # Consistent spacing between canvas and coordinates

        legend = Legend(self)
        layout.addWidget(legend)
        legend.setVisible(False)

        canvas = Canvas(self)
        layout.addWidget(canvas, 1)
        canvas.setVisible(False)

        placeholder = PlaceHolder(
            self,
            text=self.texts.placeholder,
            minimum_width=Settings.DIMENSION.MIN_WIDTH_LARGE,
            minimum_height=Settings.DIMENSION.MIN_HEIGHT_SMALL,
            stretch_widgets=False,
            icon=GenericIcons.DEVICE_PLACEHOLDER,
        )
        placeholder.setObjectName("map-placeholder")
        layout.addWidget(placeholder, 1)

        coordinates = Coordinates(self)
        layout.addWidget(coordinates)

        self.setLayout(layout)

        self.ui: MapBlock.UI = MapBlock.UI(
            legend=legend,
            canvas=canvas,
            coordinates=coordinates,
            placeholder=placeholder,
        )
        self._placeholder_helper_anim: QSequentialAnimationGroup | None = None
        self._placeholder_icon: GenericIcons = GenericIcons.DEVICE_PLACEHOLDER

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the map view."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the map view."""
        self.layout().setAlignment(self.ui.canvas, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(self.ui.coordinates, Qt.AlignmentFlag.AlignCenter)

    def _set_size_policy(self) -> None:
        """Centralize size policies for the map view and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.coordinates.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the map view and its UI widgets."""
        view_signals.RunHelperAnimationRequested.connect(self._on_run_helper_animation)
        view_signals.MapTabActivated.connect(self._on_run_helper_animation)
        view_signals.AuthentificationSucceeded.connect(self._on_connection_succeeded)
        view_signals.DeviceSelectionSucceeded.connect(self._on_connection_succeeded)
        view_signals.AuthentificationFailed.connect(self._on_authentification_failed)
        view_signals.DeviceSelectionFailed.connect(self._on_device_selection_failed)

    def is_canvas_visible(self) -> bool:
        """Return whether the concrete map canvas is currently visible."""
        return self.ui.canvas.isVisible()

    def update_placeholder(self, text: str, icon_member: GenericIcons) -> None:
        """Update the placeholder text and symbology for the given logical icon."""

        self._placeholder_icon = icon_member
        self.ui.placeholder.set_text(text)
        self.ui.placeholder.set_icon(icon_member)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh theme-dependent icons for all map block children."""
        self.ui.legend.apply_theme_icons(theme)
        self.ui.placeholder.apply_theme_icons(theme)
        self.ui.coordinates.apply_theme_icons(theme)

    def _on_connection_succeeded(self, device: dict) -> None:
        """Update placeholder after auth or device selection succeeds."""
        self.update_placeholder(
            self.texts.loading_placeholder, GenericIcons.MAP_PLACEHOLDER
        )
        self._on_run_helper_animation()

    def _on_device_selection_failed(self, device: dict) -> None:
        """Pulse placeholder when device selection fails."""
        self._on_run_helper_animation()

    def _on_authentification_failed(self, *_args) -> None:
        """Pulse placeholder when authentification fails."""
        self._on_run_helper_animation()

    def _on_run_helper_animation(self) -> None:
        """Run the placeholder helper animation."""
        if not self.ui.placeholder.isVisible():
            return  # Placeholder is not visible, no need to animate
        self._play_placeholder_helper_animation()

    def _play_placeholder_helper_animation(self) -> None:
        """
        Run a one-shot opacity pulse on the canvas placeholder. Help to draw attention of the user to the placeholder.
        """
        svg = self.ui.placeholder.findChild(SVG)
        if svg is None:
            return
        effect = svg.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(svg)
            svg.setGraphicsEffect(effect)
        if (
            self._placeholder_helper_anim is not None
            and self._placeholder_helper_anim.state()
            == QAbstractAnimation.State.Running
        ):
            self._placeholder_helper_anim.stop()
        half = Settings.ANIMATION.PLACEHOLDER_HELPER_DURATION // 2
        easing = QEasingCurve.Type.OutCubic
        anim_fade_out = QPropertyAnimation(effect, b"opacity")
        anim_fade_out.setDuration(half)
        anim_fade_out.setStartValue(1.0)
        anim_fade_out.setEndValue(0.55)
        anim_fade_out.setEasingCurve(easing)
        anim_fade_in = QPropertyAnimation(effect, b"opacity")
        anim_fade_in.setDuration(half)
        anim_fade_in.setStartValue(0.55)
        anim_fade_in.setEndValue(1.0)
        anim_fade_in.setEasingCurve(easing)
        self._placeholder_helper_anim = QSequentialAnimationGroup(self)
        self._placeholder_helper_anim.addAnimation(anim_fade_out)
        self._placeholder_helper_anim.addAnimation(anim_fade_in)
        self._placeholder_helper_anim.setLoopCount(
            Settings.ANIMATION.PLACEHOLDER_HELPER_ITERATION
        )
        self._placeholder_helper_anim.start()


Map = MapBlock
