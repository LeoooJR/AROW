"""Welcome start and recent-files block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.blocks.start.start_recent_placeholder import StartRecentPlaceholder
from gui.blocks.start.start_settings import start_settings
from gui.colors import Theme
from gui.components import File
from gui.settings import Settings
from gui.signals import signals
from gui.wrapper import VerticalLayoutWrapper


class StartRecentBlock(VerticalLayoutWrapper, Block):
    """Welcome card containing dated recent-session placeholders."""

    texts: StartRecentBlock.Text
    ui: StartRecentBlock.UI

    @dataclass(frozen=True)
    class Text:
        recent_label: Final[str] = "Recent sessions"
        recent_files: tuple[tuple[str, str, str], ...] = (
            ("kilometer-marker_128450.log", "log", "Last opened 2026-05-26"),
            ("west-yard_milestone.geojson", "geojson", "Last opened 2026-05-24"),
            ("inspection-context.kml", "kml", "Last opened 2026-05-21"),
        )

    @dataclass
    class UI:
        recent_label: QLabel
        recent_files_wrapper: VerticalLayoutWrapper
        empty_placeholder: StartRecentPlaceholder

    def __init__(self, parent: QWidget | None = None):
        """Build the welcome start/recent card and placeholder recent files."""
        block_texts = StartRecentBlock.Text()

        recent_label = QLabel(block_texts.recent_label, parent)
        recent_label.setProperty("welcome-section-title", True)

        recent_files_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        recent_files_wrapper.setObjectName("start-recent-files-wrapper")

        empty_placeholder = StartRecentPlaceholder(recent_files_wrapper)
        recent_files_wrapper.add_widget(empty_placeholder)

        super().__init__(
            parent,
            widgets=[recent_label, recent_files_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                start_settings.CARD_PADDING_LEFT,
                start_settings.CARD_PADDING_TOP,
                start_settings.CARD_PADDING_RIGHT,
                start_settings.CARD_PADDING_BOTTOM,
            ),
            stretch_at_end=True,
        )
        self.setObjectName("welcome-start-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts

        self.ui = StartRecentBlock.UI(
            recent_label=recent_label,
            recent_files_wrapper=recent_files_wrapper,
            empty_placeholder=empty_placeholder,
        )
        self._sync_empty_placeholder_visibility()
        self._finalize_ui_hooks()

    @Slot()
    def _add_recent_placeholders(self, count: int = 3) -> None:
        """Add generated recent-file display rows to the recent-files wrapper."""
        placeholder_items = self.texts.recent_files
        existing_count = len(self._recent_file_widgets())
        if 0 < existing_count < len(placeholder_items):
            return
        end_index = min(count, len(placeholder_items))
        for index in range(existing_count, end_index):
            file_name, file_type, date_text = placeholder_items[index]
            self.add_file(file_name=file_name, file_type=file_type, date_text=date_text)

    def add_file(
        self,
        file_name: str,
        file_type: str,
        date_text: str | None = None,
    ) -> File:
        """Add a recent-session file row and hide the empty placeholder if needed."""
        file_widget = File(
            self.ui.recent_files_wrapper,
            file_name=file_name,
            file_type=file_type,
            file_save=False,
            date_text=date_text,
        )
        self.ui.recent_files_wrapper.add_widget(file_widget)
        self._sync_empty_placeholder_visibility()
        return file_widget

    def remove_file(self, file_widget: File) -> None:
        """Remove a recent-session file row and show the placeholder when empty."""
        layout = self.ui.recent_files_wrapper.get_layout()
        layout.removeWidget(file_widget)
        file_widget.setParent(None)
        file_widget.deleteLater()
        self._sync_empty_placeholder_visibility()

    def _recent_file_widgets(self) -> list[File]:
        """Return active recent-session file rows."""
        layout = self.ui.recent_files_wrapper.get_layout()
        rows: list[File] = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, File):
                rows.append(widget)
        return rows

    def _sync_empty_placeholder_visibility(self) -> None:
        """Show the empty state only when no recent-session rows are present."""
        self.ui.empty_placeholder.setVisible(not self._recent_file_widgets())

    def _set_size_policy(self) -> None:
        """Set resize behavior for the card labels and recent-files wrapper."""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.recent_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.recent_files_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        """Align card labels and recent-file rows to the top-left."""
        self.ui.recent_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.ui.recent_files_wrapper.get_layout().setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

    def _connect_signals(self) -> None:
        """Connect delayed UI seed hooks."""
        signals.UI.UiConstraintsDisabled.connect(self._add_recent_placeholders)

    @property
    def recent_files_wrapper(self) -> VerticalLayoutWrapper:
        """Return the recent-files wrapper."""
        return self.ui.recent_files_wrapper

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh icons for recent-file display rows."""
        self.ui.empty_placeholder.apply_theme_icons(theme)
        lay = self.ui.recent_files_wrapper.get_layout()
        for index in range(lay.count()):
            item = lay.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, File):
                widget.apply_theme_icons(theme)


__all__ = ["StartRecentBlock"]
