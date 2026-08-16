from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout

from gui.blocks.location import MilestoneTargetBlock
from gui.blocks.start import (
    ConnectionActionsBlock,
    OperatorReadinessBlock,
    StartRecentBlock,
)
from gui.constants.colors import Theme
from gui.constants.settings import Settings
from gui.pages.welcome_settings import welcome_settings
from gui.signals import signals
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class WelcomePage(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Copy for the welcome operator briefing layout."""

        title: Final[str] = "Operator briefing"

    @dataclass
    class UI:
        """Composed widgets for the welcome screen layout."""

        briefing_card: OperatorReadinessBlock
        connection_card: ConnectionActionsBlock
        milestone_card: MilestoneTargetBlock
        start_card: StartRecentBlock
        top_row: HorizontalLayoutWrapper
        content_wrapper: VerticalLayoutWrapper

    def __init__(self, parent=None):
        """Build operator readiness, connection actions, and recent sessions.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """

        super().__init__(parent)

        self.texts = WelcomePage.Text()

        self.setObjectName("welcome-panel")
        self.setProperty("welcome-panel", True)

        briefing_card = OperatorReadinessBlock(self)
        connection_card = ConnectionActionsBlock(self)
        connection_card.show()
        milestone_card = MilestoneTargetBlock(self)
        milestone_card.hide()
        start_card = StartRecentBlock(self)

        top_row = HorizontalLayoutWrapper(
            self,
            widgets=[briefing_card, connection_card, milestone_card],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        top_row.setObjectName("welcome-top-row")
        top_layout = top_row.get_layout()
        top_layout.setStretchFactor(briefing_card, 3)
        top_layout.setStretchFactor(connection_card, 2)
        top_layout.setStretchFactor(milestone_card, 2)

        content_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[top_row, start_card],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        content_wrapper.setObjectName("welcome-content-wrapper")

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
            Settings.PANEL.CONTENT_PADDING,
        )
        layout.setSpacing(Settings.PANEL.SECTION_SPACING)
        layout.addWidget(content_wrapper)
        layout.addStretch(1)
        self.setLayout(layout)
        self._expanded_workspace_mode = False

        self.ui: WelcomePage.UI = WelcomePage.UI(
            briefing_card=briefing_card,
            connection_card=connection_card,
            milestone_card=milestone_card,
            start_card=start_card,
            top_row=top_row,
            content_wrapper=content_wrapper,
        )

        self._finalize_ui_hooks()

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.briefing_card.apply_theme_icons(theme)
        if self.ui.connection_card.isVisible():
            self.ui.connection_card.apply_theme_icons(theme)
        if self.ui.milestone_card.isVisible():
            self.ui.milestone_card.apply_theme_icons(theme)
        self.ui.start_card.apply_theme_icons(theme)

    def set_expanded_workspace_mode(self, enabled: bool) -> None:
        """Center and cap welcome content when both app sidebars are hidden."""
        if self._expanded_workspace_mode == enabled:
            return
        self._expanded_workspace_mode = enabled
        if enabled:
            self.layout().setAlignment(
                self.ui.content_wrapper,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            )
            self._apply_expanded_workspace_width()
        else:
            self.ui.content_wrapper.setMinimumWidth(0)
            self.ui.content_wrapper.setMaximumWidth(Settings.PANEL.UNBOUNDED_HEIGHT)
            self.layout().setAlignment(
                self.ui.content_wrapper, Qt.AlignmentFlag.AlignTop
            )
        self.ui.content_wrapper.updateGeometry()
        self.updateGeometry()

    def _apply_expanded_workspace_width(self) -> None:
        """Use available tab width while preventing ultra-wide card stretching."""
        target_width = min(
            welcome_settings.EXPANDED_CONTENT_MAX_WIDTH,
            max(0, self.contentsRect().width() - (Settings.PANEL.CONTENT_PADDING * 2)),
        )
        self.ui.content_wrapper.setMinimumWidth(target_width)
        self.ui.content_wrapper.setMaximumWidth(target_width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_expanded_workspace_mode", False):
            self._apply_expanded_workspace_width()

    def _finalize_ui_hooks(self) -> None:
        """Run the final UI setup hooks for the welcome panel."""
        self._set_alignment()
        self._set_size_policy()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals for the welcome panel and its UI widgets."""
        signals.DEVICE.DeviceSelectionSucceeded.connect(
            self._on_device_selection_succeeded
        )
        signals.DEVICE.RemoveActiveDeviceSucceeded.connect(
            self._on_remove_active_device_succeeded
        )

    def _set_alignment(self) -> None:
        """Centralize layout alignment for the panel and its UI widgets."""
        self.layout().setAlignment(self.ui.content_wrapper, Qt.AlignmentFlag.AlignTop)
        self.ui.content_wrapper.get_layout().setAlignment(
            self.ui.top_row, Qt.AlignmentFlag.AlignTop
        )
        self.ui.content_wrapper.get_layout().setAlignment(
            self.ui.start_card, Qt.AlignmentFlag.AlignTop
        )

    def _set_size_policy(self) -> None:
        """Centralize size policies for the panel and its UI widgets (window resizing)."""
        self.ui.briefing_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.connection_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.milestone_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.start_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.top_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.content_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    ### Slots ###

    @Slot(str, str, str)
    def _on_device_selection_succeeded(
        self, simulation_id: str, device_id: str, device_name: str
    ) -> None:
        """Handle the device selection succeeded.
        Show the milestone card and hide the connection card.
        """
        self.ui.connection_card.hide()
        self.ui.milestone_card.show()

    @Slot(str)
    def _on_remove_active_device_succeeded(self, device_id: str) -> None:
        """Handle the remove active device succeeded.
        Hide the milestone card and show the connection card.
        """
        self.ui.milestone_card.hide()
        self.ui.connection_card.show()
