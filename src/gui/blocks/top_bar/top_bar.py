"""Application top bar block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)
from shiboken6 import isValid

from gui.blocks.base import Block
from gui.colors import Theme, get_current_theme
from gui.components import SVG, ToolButton
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import GridLayoutWrapper, HorizontalLayoutWrapper


class TopBar(QWidget, Block):
    """
    Header widget of the application.
    """

    @dataclass(frozen=True)
    class Text:
        """Text used in element across the header."""

        light_palette_button_tooltip: Final[str] = "Switch to light mode"
        dark_palette_button_tooltip: Final[str] = "Switch to dark mode"
        left_panel_visibility_button_tooltip: Final[str] = (
            "Toggle left panels visibility"
        )
        right_panel_visibility_button_tooltip: Final[str] = (
            "Toggle right panels visibility"
        )

    @dataclass
    class UI:
        """UI elements used in the header widgets."""

        name: SVG
        light_palette_button: ToolButton
        dark_palette_button: ToolButton
        palette_button_group: QButtonGroup
        palette_button_wrapper: HorizontalLayoutWrapper
        palette_thumb: QFrame
        left_panel_visibility_request_button: ToolButton
        right_panel_visibility_request_button: ToolButton
        layout_buttons_wrapper: GridLayoutWrapper

    def __init__(self, parent=None):
        """Initialize the header widget.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        # Initialize parent QWidget
        super().__init__(parent)

        self.setObjectName("header")

        self.ui: TopBar.UI
        self.texts = TopBar.Text()

        # Set fixed height from settings
        self.setFixedHeight(Settings.DIMENSION.HEADER_HEIGHT)

        # Create horizontal layout for header
        layout = QHBoxLayout()

        # Create palette button group, containing light and dark mode buttons, exclusive to one of them being selected at a time
        palette_button_group = QButtonGroup(self)
        palette_button_group.setProperty("button-group", True)
        palette_button_group.setExclusive(True)
        light_palette_button = ToolButton(
            self,
            icon=GenericIcons.LIGHT_MODE,
            tooltip=self.texts.light_palette_button_tooltip,
        )
        dark_palette_button = ToolButton(
            self,
            icon=GenericIcons.DARK_MODE,
            tooltip=self.texts.dark_palette_button_tooltip,
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
        name = SVG(icon_qt_path(ApplicationIcons.NAME), self)
        name.setFixedSize(
            Settings.DIMENSION.APP_NAME_WIDTH, Settings.DIMENSION.APP_NAME_HEIGHT
        )
        # Add name to layout
        layout.addWidget(name, 1)

        # Left panels visibility button: toggles left sidebar (device + location panels). visibility=True => panels shown; at start panels are visible.
        left_panel_visibility_request_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_SIDEBAR_INSET,
            tooltip=self.texts.left_panel_visibility_button_tooltip,
        )
        left_panel_visibility_request_button.setObjectName(
            "left-panel-visibility-request-button"
        )
        left_panel_visibility_request_button.setProperty("visibility", True)
        left_panel_visibility_request_button.setProperty("inset", True)

        # Right panels visibility button: toggles right sidebar (host + log panels). visibility=True => panels shown; at start panels are visible.
        right_panel_visibility_request_button = ToolButton(
            self,
            icon=GenericIcons.LAYOUT_SIDEBAR_INSET_REVERSE,
            tooltip=self.texts.right_panel_visibility_button_tooltip,
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

        self.ui: TopBar.UI = TopBar.UI(
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

        self._finalize_ui_hooks()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the header."""
        self._connect_signals()
        self._set_alignment()
        self._set_size_policy()

    def _connect_signals(self) -> None:
        """Connect signals for the header widgets."""

        #### Signals for toggling the left and right panels visibility ####
        left_btn = self.ui.left_panel_visibility_request_button
        right_btn = self.ui.right_panel_visibility_request_button
        left_btn.clicked.connect(
            lambda: signals.UI.LeftPanelsVisibilityRequested.emit(
                not bool(left_btn.property("visibility"))
            )
        )
        right_btn.clicked.connect(
            lambda: signals.UI.RightPanelsVisibilityRequested.emit(
                not bool(right_btn.property("visibility"))
            )
        )

        #### Signals for toggling the palette ####
        self.ui.palette_button_group.buttonClicked.connect(
            self._on_palette_button_clicked
        )

    def _set_alignment(self) -> None:
        """Set the alignment of the header widgets."""
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
        """Set the size policy of the header widgets."""
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

    @property
    def left_panel_visibility_request_button(self) -> ToolButton:
        """Return the left panels visibility request button."""
        return self.ui.left_panel_visibility_request_button

    @property
    def right_panel_visibility_request_button(self) -> ToolButton:
        """Return the right panels visibility request button."""
        return self.ui.right_panel_visibility_request_button

    @property
    def light_palette_button(self) -> ToolButton:
        """Return the light palette button."""
        return self.ui.light_palette_button

    @property
    def dark_palette_button(self) -> ToolButton:
        """Return the dark palette button."""
        return self.ui.dark_palette_button

    def toggle_left_panels_visibility_request_button(self) -> None:
        """Update left panels button icon and properties to the toggled state (call after body left panels visibility has been set).

        Args:
            None

        Returns:
            None
        """
        button = self.ui.left_panel_visibility_request_button
        if button.property("inset"):
            button.setProperty("inset", False)
            button.setProperty("visibility", False)
            button.set_icon(GenericIcons.LAYOUT_SIDEBAR)
        else:
            button.setProperty("inset", True)
            button.setProperty("visibility", True)
            button.set_icon(GenericIcons.LAYOUT_SIDEBAR_INSET)

    def toggle_right_panels_visibility_request_button(self) -> None:
        """Update right panels button icon and properties to the toggled state (call after body right panels visibility has been set).

        Args:
            None

        Returns:
            None
        """
        button = self.ui.right_panel_visibility_request_button
        if button.property("inset"):
            button.setProperty("inset", False)
            button.setProperty("visibility", False)
            button.set_icon(GenericIcons.LAYOUT_SIDEBAR_REVERSE)
        else:
            button.setProperty("inset", True)
            button.setProperty("visibility", True)
            button.set_icon(GenericIcons.LAYOUT_SIDEBAR_INSET_REVERSE)

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh header chrome icon resources for ``theme``."""
        self.ui.light_palette_button.apply_theme_icons(theme)
        self.ui.dark_palette_button.apply_theme_icons(theme)
        self.ui.name.set_path(icon_qt_path_for_theme(theme, ApplicationIcons.NAME))
        left_btn = self.ui.left_panel_visibility_request_button
        left_icon = (
            GenericIcons.LAYOUT_SIDEBAR_INSET
            if left_btn.property("inset")
            else GenericIcons.LAYOUT_SIDEBAR
        )
        left_btn.set_icon(left_icon)
        left_btn.apply_theme_icons(theme)
        right_btn = self.ui.right_panel_visibility_request_button
        right_icon = (
            GenericIcons.LAYOUT_SIDEBAR_INSET_REVERSE
            if right_btn.property("inset")
            else GenericIcons.LAYOUT_SIDEBAR_REVERSE
        )
        right_btn.set_icon(right_icon)
        right_btn.apply_theme_icons(theme)

    #### Private methods ####

    def _update_palette_thumb_geometry(self) -> None:
        """Position the palette thumb over the active theme button (initial or after layout)."""
        if not isValid(self):
            return
        btn = (
            self.ui.dark_palette_button
            if get_current_theme() == "dark"
            else self.ui.light_palette_button
        )
        thumb = self.ui.palette_thumb
        if not isValid(btn) or not isValid(thumb):
            return
        tw, th = thumb.width(), thumb.height()
        g = btn.geometry()
        x = g.x() + (g.width() - tw) // 2
        y = g.y() + (g.height() - th) // 2
        thumb.setGeometry(QRect(x, y, tw, th))
        btn.raise_()

    def _on_palette_button_clicked(self, button: QAbstractButton) -> None:
        """Handle the palette button click."""

        ### Palette button signal emission ###
        if button == self.ui.light_palette_button:
            signals.UI.UpdatePaletteSignal.emit("light")
        elif button == self.ui.dark_palette_button:
            signals.UI.UpdatePaletteSignal.emit("dark")

        ### Palette thumb animation (move the thumb over the clicked button) ###
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
        button.raise_()
