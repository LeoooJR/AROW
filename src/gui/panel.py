"""Shared side-panel abstractions."""

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from gui.colors import Theme
from gui.components import LeadingIconLabel
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
    """Static chrome for a side panel shell."""

    object_name: str
    title: str
    title_icon: PanelIcon
    body_stretch: int = 1


class CollapsiblePanel(QFrame, ABC, metaclass=QtABCMeta):
    """Common shell for side panels with a title header and body."""

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

        self._panel_header = QWidget(self)
        self._panel_header.setProperty("panel-title", True)
        self._panel_header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(self._panel_header)
        header_layout.setContentsMargins(*Settings.SPACING.MARGIN_NONE)
        header_layout.setSpacing(Settings.SPACING.NONE)
        header_layout.addWidget(self._panel_title, 1)
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
            self._panel_title,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )
        self._set_body_alignment()

    def _connect_signals(self) -> None:
        """Wire subclass-specific signals."""
        self._connect_body_signals()

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh shared chrome icons and subclass-owned icons."""
        self._panel_title.apply_theme_icons(theme)
        self._apply_body_theme_icons(theme)

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
