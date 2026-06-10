"""Location side panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.blocks.location import MilestoneTargetBlock
from gui.colors import Theme
from gui.components import LeadingIconLabel, ToolButton
from gui.icons import GenericIcons
from gui.panel import CollapsiblePanel, CollapsiblePanelConfig
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import VerticalLayoutWrapper


class LocationPanel(CollapsiblePanel):
    """Panel that displays and requests the milestone target."""

    @dataclass(frozen=True)
    class Text:
        """Panel-owned labels and tooltips."""

        title: Final[str] = "Location"
        expand_button_tooltip: Final[str] = "Toggle panel visibility"

    @dataclass
    class UI:
        """Panel chrome and composed location block."""

        title: LeadingIconLabel
        expand_button: ToolButton
        header: QWidget
        body: VerticalLayoutWrapper
        milestone_target_block: MilestoneTargetBlock

    def __init__(self, parent: QWidget | None = None):
        """Build the location panel shell and milestone target block.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        self.texts = LocationPanel.Text()
        self.ui: LocationPanel.UI
        self._milestone_target_block: MilestoneTargetBlock
        super().__init__(
            CollapsiblePanelConfig(
                object_name="location-panel",
                title=self.texts.title,
                title_icon=GenericIcons.GEO,
                expanded_icon=GenericIcons.LAYOUT_BOTTOMBAR_INSET,
                collapsed_icon=GenericIcons.LAYOUT_BOTTOMBAR,
                visibility_signal=signals.UI.LocationPanelVisibilityRequested,
                expand_button_tooltip=self.texts.expand_button_tooltip,
            ),
            parent,
        )
        self.ui = LocationPanel.UI(
            title=self.panel_title,
            expand_button=self.expand_button,
            header=self.header,
            body=self.body,
            milestone_target_block=self._milestone_target_block,
        )

    def _build_body(self) -> VerticalLayoutWrapper:
        """Build the location body as a reusable block host."""
        self._milestone_target_block = MilestoneTargetBlock(self)
        body = VerticalLayoutWrapper(
            self,
            widgets=[self._milestone_target_block],
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        body.get_layout().setStretchFactor(self._milestone_target_block, 1)
        return body

    def _set_body_alignment(self) -> None:
        """Location body uses layout stretch to size the milestone block."""
        pass

    def _set_body_size_policy(self) -> None:
        """Centralize size policies for panel-owned widgets."""
        self.body.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._milestone_target_block.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def _connect_body_signals(self) -> None:
        """Location panel body has no panel-owned signal wiring."""
        pass

    def _apply_body_theme_icons(self, theme: Theme) -> None:
        """Refresh location block icon-bearing controls for ``theme``."""
        self._milestone_target_block.apply_theme_icons(theme)
