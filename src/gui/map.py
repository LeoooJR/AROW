"""
This file contains all graphical elements related to the map panel.
"""

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

from gui.colors import get_current_palette
from gui.elements import SVG, IconLabel, PanelTitle, PlaceHolder, ToolButton
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import app_signals
from gui.svg import get_svg_size
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

        location_label_icon: IconLabel
        simulated_location_label_icon: IconLabel
        legend_first_row: HorizontalLayoutWrapper
        kilometric_point_label_icon: IconLabel
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

        location_label_icon = IconLabel(
            None,
            icon_path=GenericIcons.LOCATION.value,
            text=self.texts.location_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        simulated_location_label_icon = IconLabel(
            None,
            icon_path=GenericIcons.FAKE_LOCATION.value,
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

        kilometric_point_label_icon = IconLabel(
            None,
            icon_path=GenericIcons.MILESTONE.value,
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
        palette = get_current_palette()
        latitude_widget.setStyleSheet(
            f"QWidget#location-latitude-widget {{ background-color: {palette.WHITE}; border: 1px solid {palette.PANEL_BORDER}; border-radius: {Settings.BORDER_RADIUS.SM}px; }}"
        )
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
        latitude_label.setStyleSheet(
            f"background-color: {palette.TRANSPARENT}; color: {palette.HELPER_TEXT}; font-size: {Settings.LOCATION.LABEL_FONT_SIZE}px;"
        )
        latitude_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_SMALL, QFont.Weight.Normal)
        )
        latitude_label_font_size = latitude_label.font().pointSize()

        if icon_path is not None:
            svg = SVG(icon_path, self)
            svg_size = get_svg_size(Settings.FONT.SIZE_DEFAULT)
            svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            svg.setFixedSize(svg_size)
            layout.addWidget(svg)

        latitude_widget.layout().addWidget(latitude_label)

        longitude_widget = QWidget(self)
        longitude_widget.setObjectName("location-longitude-widget")
        longitude_widget.setStyleSheet(
            f"QWidget#location-longitude-widget {{ background-color: {palette.WHITE}; border: 1px solid {palette.PANEL_BORDER}; border-radius: {Settings.BORDER_RADIUS.SM}px; }}"
        )
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
        longitude_label.setStyleSheet(
            f"background-color: {palette.TRANSPARENT}; color: {palette.HELPER_TEXT}; font-size: {Settings.LOCATION.LABEL_FONT_SIZE}px;"
        )
        longitude_label.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_SMALL, QFont.Weight.Normal)
        )
        longitude_widget.layout().addWidget(longitude_label)

        layout.addWidget(latitude_widget)
        layout.addWidget(longitude_widget)

        crosshair_button = ToolButton(
            parent=self,
            icon_path=GenericIcons.CROSSHAIR.value,
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
        pass

    def clear_longitude(self):
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
        simulation_state_off: IconLabel
        simulation_state_on: IconLabel
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

        simulation_state_off = IconLabel(
            self,
            icon_path=GenericIcons.OFF.value,
            text=self.texts.simulation_state_off,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        simulation_state_on = IconLabel(
            self,
            icon_path=GenericIcons.ON.value,
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
            icon_path=GenericIcons.PLAY.value,
            icon_size=get_svg_size(Settings.FONT.SIZE_DEFAULT),
            tooltip=self.texts.play_button_tooltip,
        )
        play_button.setEnabled(True)
        play_button.setProperty("toggle", False)
        play_button.clicked.connect(self._on_play_button_clicked)
        layout.addWidget(play_button)

        location_widget = Location(self, GenericIcons.LOCATION.value)
        layout.addWidget(location_widget)

        simulated_location_widget = Location(self, GenericIcons.FAKE_LOCATION.value)
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
            self.ui.play_button.set_icon(
                GenericIcons.PAUSE.value, Settings.FONT.SIZE_DEFAULT
            )
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
            self.ui.play_button.set_icon(
                GenericIcons.PLAY.value, Settings.FONT.SIZE_DEFAULT
            )
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


class Map(QWidget):
    """Map view: canvas/placeholder (expandable) and coordinates bar."""

    @dataclass(frozen=True)
    class Text:
        """Placeholder copy when the map cannot load yet."""

        placeholder: Final[str] = "Select a device to get started..."

    @dataclass
    class UI:
        """Canvas, coordinates strip, and empty-state placeholder."""

        canvas: Canvas
        coordinates: Coordinates
        placeholder: PlaceHolder

    def __init__(self, parent=None):
        """Lay out placeholder, hidden canvas, and coordinates bar.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: Map.UI
        self.texts = Map.Text()

        layout = QVBoxLayout()
        layout.setContentsMargins(
            *Settings.SPACING.MARGIN_NONE
        )  # Padding handled by parent
        layout.setSpacing(
            Settings.MAP.MAP_SPACING
        )  # Consistent spacing between canvas and coordinates

        canvas = Canvas(self)
        layout.addWidget(canvas, 1)
        canvas.setVisible(False)

        placeholder = PlaceHolder(
            self,
            text=self.texts.placeholder,
            minimum_width=Settings.DIMENSION.MIN_WIDTH_LARGE,
            minimum_height=Settings.DIMENSION.MIN_HEIGHT_SMALL,
            stretch_widgets=False,
            icon_path=GenericIcons.DEVICE_PLACEHOLDER.value,
        )
        placeholder.setObjectName("map-placeholder")
        layout.addWidget(placeholder, 1)

        coordinates = Coordinates(self)
        layout.addWidget(coordinates)

        self.setLayout(layout)

        self.ui: Map.UI = Map.UI(
            canvas=canvas, coordinates=coordinates, placeholder=placeholder
        )
        self._placeholder_helper_anim: QSequentialAnimationGroup | None = None

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
        pass

    def is_canvas_visible(self) -> bool:
        return self.ui.canvas.isVisible()

    def update_placeholder(self, text: str, icon_path: str) -> None:
        """Update the placeholder text and icon.

        Args:
            text: Message shown in the empty state.
            icon_path: Asset path for the placeholder illustration.
        """
        self.ui.placeholder.set_text(text)
        self.ui.placeholder.set_icon(icon_path)

    def play_placeholder_helper_animation(self) -> None:
        """
        Run a one-shot opacity pulse on the placeholder phone icon to remind the user
        to connect their device before the map can load. Called when the map tab is
        shown and progress is still 0 (map not loaded yet).
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


class MapPanel(QFrame):
    """
    Panel that displays the map view.
    """

    @dataclass(frozen=True)
    class Text:
        """Panel title and loading placeholder for the map tab."""

        title: Final[str] = "Map"
        loading_placeholder: Final[str] = "Map is being loaded..."

    @dataclass
    class UI:
        """Title, optional legend, and embedded map widget."""

        title: PanelTitle
        legend: Legend
        map: Map

    def __init__(self, parent=None):
        """Build the framed map panel with title and legend hook.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)

        self.ui: MapPanel.UI
        self.texts = MapPanel.Text()

        self.setObjectName("map-panel")
        self.setProperty("main-panel", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(
            Settings.PANEL.SECTION_SPACING
        )  # Consistent spacing between major sections

        title = PanelTitle(
            parent=self, text=self.texts.title, icon_path=GenericIcons.MAP.value
        )
        title.setProperty("main-panel-title", True)
        layout.addWidget(title)

        legend = Legend(self)
        layout.addWidget(legend)
        legend.setVisible(False)

        map = Map(self)
        layout.addWidget(map, 1)
        map.setVisible(True)

        self.setLayout(layout)

        self.ui: MapPanel.UI = MapPanel.UI(title=title, legend=legend, map=map)

        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        pass

    def _connect_signals(self) -> None:
        """Connect signals for the map panel and its UI widgets."""
        #### Signals for handling the step transition from authentification to map display ####
        app_signals.AuthentificationSucceeded.connect(self._on_device_connected)
        app_signals.DeviceSelectionSucceeded.connect(self._on_device_connected)
        app_signals.AuthentificationFailed.connect(self._on_authentification_failed)

    def _on_device_connected(self, device: str) -> None:
        """Handle map UI updates for any successful connection flow."""
        self.ui.map.update_placeholder(
            self.texts.loading_placeholder, GenericIcons.MAP_PLACEHOLDER.value
        )
        self.ui.map.play_placeholder_helper_animation()

    def _on_authentification_failed(self) -> None:
        """Handle the authentification failed event."""
        self.ui.map.play_placeholder_helper_animation()

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ui.title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.legend.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.map.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def is_map_visible(self) -> bool:
        return self.ui.map.is_canvas_visible()

    def helper(self) -> None:
        """Run the one-shot helper animation (e.g. placeholder phone icon pulse) when the map tab is displayed."""
        self.ui.map.play_placeholder_helper_animation()
