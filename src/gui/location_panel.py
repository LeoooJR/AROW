"""
This file contains all graphical elements related to the location settings.
"""

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.colors import Theme
from gui.components import (
    Button,
    DemiBoldText,
    FileOpenDialog,
    HelperText,
    LeadingIconLabel,
    SelectionField,
    ToolButton,
    WarningDialog,
)
from gui.icons import GenericIcons
from gui.panel import CollapsiblePanel, CollapsiblePanelConfig
from gui.settings import Settings
from gui.signals import view_signals
from gui.wrapper import VerticalLayoutWrapper


class LocationPanel(CollapsiblePanel):
    """
    Panel that displays the location settings.
    """

    @dataclass(frozen=True)
    class Text:
        """Labels, tooltips, and dialog copy for the location panel."""

        title: Final[str] = "Location"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"
        railway_label: Final[str] = "Railway"
        railway_input: Final[str] = "Select a railway"
        railway_helper_text: Final[str] = "Select a railway to get started"
        kilometric_label: Final[str] = "Kilometric point"
        kilometric_input: Final[str] = "Select a kilometric point"
        kilometric_helper_text: Final[str] = "Select a kilometric point to get started"
        start_simulation_button: Final[str] = "Start simulation"
        start_simulation_dialog_title: Final[str] = "Start simulation"
        start_simulation_dialog_text: Final[str] = (
            "Are you sure you want to start the simulation?"
        )
        start_simulation_dialog_detailed_text: Final[str] = (
            "This action will launch the simulation and start the devices."
        )

    @dataclass
    class UI:
        """Widgets for the location panel header and form body."""

        title: LeadingIconLabel
        expand_button: ToolButton
        header: QWidget
        body: QWidget
        railway_label: DemiBoldText
        railway_label_icon: LeadingIconLabel
        railway_input: SelectionField
        railway_helper_text: HelperText
        railway_input_wrapper: VerticalLayoutWrapper
        kilometric_label: DemiBoldText
        kilometric_label_icon: LeadingIconLabel
        kilometric_input: SelectionField
        kilometric_helper_text: HelperText
        kilometric_input_wrapper: VerticalLayoutWrapper
        start_simulation_button: Button

    def __init__(self, parent=None):
        """Build the location panel with inputs and simulation action.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = LocationPanel.Text()
        self.ui: LocationPanel.UI
        self._railway_label: DemiBoldText
        self._railway_label_icon: LeadingIconLabel
        self._railway_input: SelectionField
        self._railway_helper_text: HelperText
        self._railway_input_wrapper: VerticalLayoutWrapper
        self._kilometric_label: DemiBoldText
        self._kilometric_label_icon: LeadingIconLabel
        self._kilometric_input: SelectionField
        self._kilometric_helper_text: HelperText
        self._kilometric_input_wrapper: VerticalLayoutWrapper
        self._start_simulation_button: Button
        super().__init__(
            CollapsiblePanelConfig(
                object_name="location-panel",
                title=self.texts.title,
                title_icon=GenericIcons.GEO,
                expanded_icon=GenericIcons.LAYOUT_BOTTOMBAR_INSET,
                collapsed_icon=GenericIcons.LAYOUT_BOTTOMBAR,
                visibility_signal=view_signals.LocationPanelVisibilityRequested,
                expand_button_tooltip=self.texts.expand_button_tooltip,
            ),
            parent,
        )
        self.ui = LocationPanel.UI(
            title=self.panel_title,
            expand_button=self.expand_button,
            header=self.header,
            body=self.body,
            railway_label=self._railway_label,
            railway_label_icon=self._railway_label_icon,
            railway_input=self._railway_input,
            railway_helper_text=self._railway_helper_text,
            railway_input_wrapper=self._railway_input_wrapper,
            kilometric_label=self._kilometric_label,
            kilometric_label_icon=self._kilometric_label_icon,
            kilometric_input=self._kilometric_input,
            kilometric_helper_text=self._kilometric_helper_text,
            kilometric_input_wrapper=self._kilometric_input_wrapper,
            start_simulation_button=self._start_simulation_button,
        )

    def _build_body(self) -> QWidget:
        """Build the location form body."""
        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        body_layout.setSpacing(Settings.PANEL.SECTION_SPACING)

        self._railway_label = DemiBoldText(None, self.texts.railway_label)
        self._railway_label_icon = LeadingIconLabel(
            None,
            icon=GenericIcons.RAILWAY,
            text=self._railway_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        self._railway_input = SelectionField(None, self.texts.railway_input)
        self._railway_helper_text = HelperText(self, self.texts.railway_helper_text)
        self._railway_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[
                self._railway_label_icon,
                self._railway_input,
                self._railway_helper_text,
            ],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        self._railway_input_wrapper.setObjectName("railway-input-wrapper")
        self._railway_input_wrapper.setProperty("section-divider-bottom", True)
        body_layout.addWidget(self._railway_input_wrapper)

        self._kilometric_label = DemiBoldText(None, self.texts.kilometric_label)
        self._kilometric_label_icon = LeadingIconLabel(
            None,
            icon=GenericIcons.MILESTONE,
            text=self._kilometric_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        self._kilometric_input = SelectionField(self, self.texts.kilometric_input)
        self._kilometric_helper_text = HelperText(
            self, self.texts.kilometric_helper_text
        )
        self._kilometric_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[
                self._kilometric_label_icon,
                self._kilometric_input,
                self._kilometric_helper_text,
            ],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        self._kilometric_input_wrapper.setObjectName("kilometric-input-wrapper")
        self._kilometric_input_wrapper.setProperty("section-divider-bottom", True)
        body_layout.addWidget(self._kilometric_input_wrapper)

        self._start_simulation_button = Button(
            self,
            self.texts.start_simulation_button,
            icon=GenericIcons.START,
        )
        body_layout.addWidget(self._start_simulation_button)
        return body

    def _set_body_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self._railway_input_wrapper.get_layout().setAlignment(
            self._railway_label_icon, Qt.AlignmentFlag.AlignCenter
        )
        self._railway_input_wrapper.get_layout().setAlignment(
            self._railway_input, Qt.AlignmentFlag.AlignCenter
        )
        self._railway_input_wrapper.get_layout().setAlignment(
            self._railway_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.body.layout().setAlignment(
            self._railway_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self._kilometric_input_wrapper.get_layout().setAlignment(
            self._kilometric_label_icon, Qt.AlignmentFlag.AlignCenter
        )
        self._kilometric_input_wrapper.get_layout().setAlignment(
            self._kilometric_input, Qt.AlignmentFlag.AlignCenter
        )
        self._kilometric_input_wrapper.get_layout().setAlignment(
            self._kilometric_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.body.layout().setAlignment(
            self._kilometric_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.body.layout().setAlignment(
            self._start_simulation_button, Qt.AlignmentFlag.AlignCenter
        )

    def _set_body_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._railway_label_icon.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._railway_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._railway_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._kilometric_label_icon.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._kilometric_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._kilometric_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_body_signals(self) -> None:
        """Connect signals for the location panel and its UI widgets."""
        self._start_simulation_button.clicked.connect(self._on_simulation_start)

    def _apply_body_theme_icons(self, theme: Theme) -> None:
        self._railway_label_icon.apply_theme_icons(theme)
        self._kilometric_label_icon.apply_theme_icons(theme)
        self._start_simulation_button.apply_theme_icons(theme)

    def open_file_dialog(self) -> None:
        """Open the file dialog."""

        dialog = FileOpenDialog(self)

        if dialog.exec():

            filename = dialog.selectedFiles()

            if filename:

                print(filename)

    def _on_simulation_start(self) -> None:
        """Handle the simulation start button click event."""

        dialog = WarningDialog(
            self,
            title=self.texts.start_simulation_dialog_title,
            text=self.texts.start_simulation_dialog_text,
            detailed_text=self.texts.start_simulation_dialog_detailed_text,
        )

        button = dialog.exec()

        if button == QMessageBox.StandardButton.Yes:

            print("Simulation has started.")

        else:

            print("Launch of simulation has been canceled.")
