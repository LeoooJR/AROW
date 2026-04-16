"""
This file contains all graphical elements related to the location settings.
"""

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.elements import (
    Button,
    DemiBoldText,
    FileOpenDialog,
    HelperText,
    IconLabel,
    PanelTitle,
    PlaceHolder,
    SelectionField,
    ToolButton,
    WarningDialog,
)
from gui.icons import GenericIcons
from gui.settings import Settings
from gui.signals import app_signals
from gui.wrapper import VerticalLayoutWrapper


class LocationPanel(QFrame):
    """
    Panel that displays the location settings.
    """

    @dataclass(frozen=True)
    class Text:
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

        title: PanelTitle
        expand_button: ToolButton
        header: QWidget
        body: QWidget
        railway_label: DemiBoldText
        railway_label_icon: IconLabel
        railway_input: SelectionField
        railway_helper_text: HelperText
        railway_input_wrapper: VerticalLayoutWrapper
        kilometric_label: DemiBoldText
        kilometric_label_icon: IconLabel
        kilometric_input: SelectionField
        kilometric_helper_text: HelperText
        kilometric_input_wrapper: VerticalLayoutWrapper
        start_simulation_button: Button

    def __init__(self, parent=None):
        super().__init__(parent)

        self.ui: LocationPanel.UI
        self.texts = LocationPanel.Text()

        self.setObjectName("location-panel")
        self.setProperty("panel", True)

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
            parent=self, text=self.texts.title, icon_path=GenericIcons.GEO.value
        )
        expand_button = ToolButton(
            self,
            icon_path=GenericIcons.LAYOUT_BOTTOMBAR_INSET.value,
            tooltip=self.texts.expand_button_tooltip,
        )
        expand_button.setProperty("toggle", True)
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        header_layout.setSpacing(Settings.SPACING.NONE)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(expand_button)
        layout.addWidget(header)

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        body_layout.setSpacing(Settings.PANEL.SECTION_SPACING)

        # table_placeholder = PlaceHolder(None, "No data available", minimum_width=Settings.DIMENSION.MIN_WIDTH_LARGE, minimum_height=Settings.DIMENSION.MIN_HEIGHT_SMALL, stretch_widgets=True)
        # table_placeholder.setObjectName("table-placeholder")
        # table_placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # table_helper_text = HelperText(None, "Upload a railway context file to get started")
        # table_helper_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # table_wrapper = VerticalLayoutWrapper(self, widgets=[table_placeholder, table_helper_text], spacing=Settings.SPACING.XS, margins=Settings.SPACING.MARGIN_NONE)
        # table_wrapper.setObjectName("table-wrapper")
        # table_wrapper.layout().setAlignment(table_placeholder, Qt.AlignmentFlag.AlignCenter)
        # table_wrapper.layout().setAlignment(table_helper_text, Qt.AlignmentFlag.AlignLeft)
        # body_layout.addWidget(table_wrapper, 1)

        # upload_button = Button(self, "Upload", icon_path=GenericIcons.UPLOAD.value)
        # body_layout.addWidget(upload_button)
        # body_layout.setAlignment(upload_button, Qt.AlignmentFlag.AlignCenter)

        # Railway section with divider
        railway_label = DemiBoldText(None, self.texts.railway_label)
        railway_label_icon = IconLabel(
            None,
            icon_path=GenericIcons.RAILWAY.value,
            text=railway_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )

        railway_input = SelectionField(None, self.texts.railway_input)

        railway_helper_text = HelperText(self, self.texts.railway_helper_text)

        railway_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[railway_label_icon, railway_input, railway_helper_text],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        railway_input_wrapper.setObjectName("railway-input-wrapper")
        railway_input_wrapper.setProperty("section-divider-bottom", True)

        body_layout.addWidget(railway_input_wrapper)

        # Kilometric section with divider
        kilometric_label = DemiBoldText(None, self.texts.kilometric_label)
        kilometric_label_icon = IconLabel(
            None,
            icon_path=GenericIcons.MILESTONE.value,
            text=kilometric_label,
            spacing=Settings.SPACING.ICON_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )

        kilometric_input = SelectionField(self, self.texts.kilometric_input)

        kilometric_helper_text = HelperText(self, self.texts.kilometric_helper_text)

        kilometric_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[kilometric_label_icon, kilometric_input, kilometric_helper_text],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        kilometric_input_wrapper.setObjectName("kilometric-input-wrapper")
        kilometric_input_wrapper.setProperty("section-divider-bottom", True)

        body_layout.addWidget(kilometric_input_wrapper)

        start_simulation_button = Button(
            self, self.texts.start_simulation_button, icon_path=GenericIcons.START.value
        )
        body_layout.addWidget(start_simulation_button)

        layout.addWidget(body, 1)
        self.setLayout(layout)

        self.ui: LocationPanel.UI = LocationPanel.UI(
            title=title,
            expand_button=expand_button,
            header=header,
            body=body,
            railway_label=railway_label,
            railway_label_icon=railway_label_icon,
            railway_input=railway_input,
            railway_helper_text=railway_helper_text,
            railway_input_wrapper=railway_input_wrapper,
            kilometric_label=kilometric_label,
            kilometric_label_icon=kilometric_label_icon,
            kilometric_input=kilometric_input,
            kilometric_helper_text=kilometric_helper_text,
            kilometric_input_wrapper=kilometric_input_wrapper,
            start_simulation_button=start_simulation_button,
        )

        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.ui.header.layout().setAlignment(
            self.ui.expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self.ui.railway_input_wrapper.get_layout().setAlignment(
            self.ui.railway_label_icon, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.railway_input_wrapper.get_layout().setAlignment(
            self.ui.railway_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.railway_input_wrapper.get_layout().setAlignment(
            self.ui.railway_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.body.layout().setAlignment(
            self.ui.railway_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.kilometric_input_wrapper.get_layout().setAlignment(
            self.ui.kilometric_label_icon, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.kilometric_input_wrapper.get_layout().setAlignment(
            self.ui.kilometric_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.kilometric_input_wrapper.get_layout().setAlignment(
            self.ui.kilometric_helper_text, Qt.AlignmentFlag.AlignLeft
        )
        self.ui.body.layout().setAlignment(
            self.ui.kilometric_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.body.layout().setAlignment(
            self.ui.start_simulation_button, Qt.AlignmentFlag.AlignCenter
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.ui.header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.ui.railway_label_icon.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.railway_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.railway_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.kilometric_label_icon.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.kilometric_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.kilometric_helper_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _connect_signals(self) -> None:
        """Connect signals for the location panel and its UI widgets."""
        # self.ui.upload_button.clicked.connect(self.open_file_dialog)
        self.ui.start_simulation_button.clicked.connect(self._on_simulation_start)
        self.ui.expand_button.clicked.connect(self.toggle_panel_visibility)
        self.ui.expand_button.clicked.connect(
            lambda: app_signals.LocationPanelVisibilityRequested.emit(
                self.is_panel_visible()
            )
        )

    def is_panel_visible(self) -> bool:
        """Check if the location panel is visible."""
        return self.ui.body.isVisible()

    def _reduced_height(self) -> int:
        height = self.ui.header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def show_panel(self) -> None:
        """Show the location panel."""
        if not self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(
                QIcon(GenericIcons.LAYOUT_BOTTOMBAR_INSET.value)
            )
            self.ui.body.setVisible(True)
            self.setMaximumHeight(Settings.PANEL.UNBOUNDED_HEIGHT)
            self.updateGeometry()

    def hide_panel(self) -> None:
        """Hide the location panel."""
        if self.is_panel_visible():
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_BOTTOMBAR.value))
            self.ui.body.setVisible(False)
            self.setMaximumHeight(self._reduced_height())
            self.updateGeometry()

    def toggle_panel_visibility(self) -> None:
        """Toggle the visibility of the location panel."""
        if self.ui.expand_button.property("toggle"):
            # Reduce: hide body and constrain height so the panel under can grow.
            self.ui.expand_button.setProperty("toggle", False)
            self.ui.expand_button.setIcon(QIcon(GenericIcons.LAYOUT_BOTTOMBAR.value))
            self.ui.body.setVisible(False)
            self.setMaximumHeight(self._reduced_height())
        else:
            # Expand: show body and allow it to grow.
            self.ui.expand_button.setProperty("toggle", True)
            self.ui.expand_button.setIcon(
                QIcon(GenericIcons.LAYOUT_BOTTOMBAR_INSET.value)
            )
            self.ui.body.setVisible(True)
            self.setMaximumHeight(Settings.PANEL.UNBOUNDED_HEIGHT)
        self.updateGeometry()

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
