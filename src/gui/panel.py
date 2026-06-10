"""Shared side-panel abstractions."""

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from gui.animation import animate_widget_visibility
from gui.colors import Theme
from gui.components import LeadingIconLabel, ToolButton
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
)
from gui.settings import Settings


class QtABCMeta(type(QObject), ABCMeta):  # type: ignore[misc]
    """Merge QObject's metaclass with ``ABCMeta`` for Qt-backed panels."""

    pass


PanelIcon = GenericIcons | OperatingSystemIcons | ApplicationIcons


@dataclass(frozen=True)
class CollapsiblePanelConfig:
    """Static chrome and visibility behavior for a collapsible side panel."""

    object_name: str
    title: str
    title_icon: PanelIcon
    expanded_icon: PanelIcon
    collapsed_icon: PanelIcon
    visibility_signal: Any
    expand_button_tooltip: str = "Toggle panel visibility"
    body_stretch: int = 1


class CollapsiblePanel(QFrame, ABC, metaclass=QtABCMeta):
    """Common shell for side panels with a title, toggle button, and body."""

    def __init__(self, config: CollapsiblePanelConfig, parent: QWidget | None = None):
        """Build shared panel chrome and delegate body construction to subclasses."""
        super().__init__(parent)
        self._panel_config = config

        self.setObjectName(config.object_name)
        self.setProperty("panel", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(Settings.PANEL.SECTION_SPACING)

        self._panel_title = LeadingIconLabel(
            parent=self,
            icon=config.title_icon,
            text=config.title,
            font_size=Settings.FONT.SIZE_TITLE,
            font_weight=QFont.Weight.DemiBold,
            spacing=Settings.PANEL.TITLE_ICON_SPACING,
            margins=(
                Settings.PANEL.TITLE_PADDING_LEFT,
                Settings.PANEL.TITLE_PADDING_TOP,
                Settings.PANEL.TITLE_PADDING_RIGHT,
                Settings.PANEL.TITLE_PADDING_BOTTOM,
            ),
            text_alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label_properties={"section-title": True},
            constrain_to_size_hint=True,
        )

        self._panel_expand_button = ToolButton(
            self,
            icon=config.expanded_icon,
            tooltip=config.expand_button_tooltip,
        )
        self._panel_expand_button.setProperty("toggle", True)

        self._panel_header = QWidget(self)
        self._panel_header.setProperty("panel-title", True)
        self._panel_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(self._panel_header)
        header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        header_layout.setSpacing(Settings.SPACING.NONE)
        header_layout.addWidget(self._panel_title, 1)
        header_layout.addWidget(self._panel_expand_button)
        layout.addWidget(self._panel_header)

        self._panel_body = self._build_body()
        layout.addWidget(self._panel_body, config.body_stretch)

        self.setLayout(layout)
        self._finalize_ui_hooks()

    @property
    def panel_title(self) -> LeadingIconLabel:
        """Return the panel title widget."""
        return self._panel_title

    @property
    def expand_button(self) -> ToolButton:
        """Return the panel expand/collapse button."""
        return self._panel_expand_button

    @property
    def header(self) -> QWidget:
        """Return the panel header widget."""
        return self._panel_header

    @property
    def body(self) -> QWidget:
        """Return the panel body widget."""
        return self._panel_body

    def _finalize_ui_hooks(self) -> None:
        """Run shared and subclass setup hooks."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    def _set_size_policy(self) -> None:
        """Set shared panel size policies, then delegate body-specific policies."""
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._panel_header.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._set_body_size_policy()

    def _set_alignment(self) -> None:
        """Align shared chrome, then delegate body-specific alignment."""
        self._panel_header.layout().setAlignment(
            self._panel_expand_button,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )
        self._set_body_alignment()

    def _connect_signals(self) -> None:
        """Wire shared visibility behavior and subclass-specific signals."""
        self._panel_expand_button.clicked.connect(self.toggle_panel_visibility)
        self._panel_expand_button.clicked.connect(
            lambda: self._panel_config.visibility_signal.emit(self.is_panel_visible())
        )
        self._connect_body_signals()

    def is_panel_visible(self) -> bool:
        """Return whether the panel body is currently expanded."""
        return bool(self._panel_expand_button.property("toggle"))

    def show_panel(self) -> None:
        """Expand the panel body."""
        if not self.is_panel_visible():
            self._set_panel_visible(True)
        self._after_panel_visibility_changed()

    def hide_panel(self) -> None:
        """Collapse the panel body."""
        if self.is_panel_visible():
            self._set_panel_visible(False)
        self._after_panel_visibility_changed()

    def toggle_panel_visibility(self) -> None:
        """Toggle the panel body visibility."""
        if self.is_panel_visible():
            self.hide_panel()
        else:
            self.show_panel()
        self.updateGeometry()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh shared chrome icons and subclass-owned icons."""
        self._panel_title.apply_theme_icons(theme)
        self._panel_expand_button.set_icon(self._current_toggle_icon())
        self._panel_expand_button.apply_theme_icons(theme)
        self._apply_body_theme_icons(theme)

    def _set_panel_visible(self, visible: bool) -> None:
        """Apply toggle state, icon, and animated body visibility."""
        self._panel_expand_button.setProperty("toggle", visible)
        self._panel_expand_button.set_icon(
            self._panel_config.expanded_icon
            if visible
            else self._panel_config.collapsed_icon
        )
        animate_widget_visibility(
            self,
            visible=visible,
            axis="vertical",
            collapsed_size=self._reduced_height(),
            content_widget=self._panel_body,
        )

    def _current_toggle_icon(self) -> PanelIcon:
        """Return the icon matching the current toggle state."""
        return (
            self._panel_config.expanded_icon
            if self.is_panel_visible()
            else self._panel_config.collapsed_icon
        )

    def _reduced_height(self) -> int:
        """Height of the panel when collapsed to its header."""
        height = self._panel_header.sizeHint().height()
        if height <= 0:
            height = Settings.DIMENSION.TOOLBUTTON_HEIGHT
        return 2 * Settings.PANEL.CONTENT_PADDING + height

    def _after_panel_visibility_changed(self) -> None:
        """Hook for panels that need post-toggle refresh work."""
        pass

    @abstractmethod
    def _build_body(self) -> QWidget:
        """Build and return the concrete panel body."""
        ...

    @abstractmethod
    def _set_body_size_policy(self) -> None:
        """Set size policies for body-owned widgets."""
        ...

    @abstractmethod
    def _set_body_alignment(self) -> None:
        """Set alignment for body-owned widgets."""
        ...

    @abstractmethod
    def _connect_body_signals(self) -> None:
        """Connect body-owned signals."""
        ...

    @abstractmethod
    def _apply_body_theme_icons(self, theme: Theme) -> None:
        """Refresh icons owned by the concrete panel body."""
        ...
