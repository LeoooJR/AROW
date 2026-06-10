"""Welcome start and recent-files block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.colors import Theme
from gui.components import File
from gui.settings import Settings
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

        super().__init__(
            parent,
            widgets=[recent_label, recent_files_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                Settings.WELCOME.CARD_PADDING_LEFT,
                Settings.WELCOME.CARD_PADDING_TOP,
                Settings.WELCOME.CARD_PADDING_RIGHT,
                Settings.WELCOME.CARD_PADDING_BOTTOM,
            ),
            stretch_at_end=True,
        )
        self.setObjectName("welcome-start-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts

        self.ui = StartRecentBlock.UI(
            recent_label=recent_label,
            recent_files_wrapper=recent_files_wrapper,
        )
        self._add_recent_placeholders(count=3)
        self._finalize_ui_hooks()

    def _add_recent_placeholders(self, count: int = 3) -> None:
        """Add generated recent-file display rows to the recent-files wrapper."""
        placeholder_items = self.texts.recent_files
        for index in range(min(count, len(placeholder_items))):
            file_name, file_type, date_text = placeholder_items[index]
            self.ui.recent_files_wrapper.add_widget(
                File(
                    self.ui.recent_files_wrapper,
                    file_name=file_name,
                    file_type=file_type,
                    file_save=False,
                    date_text=date_text,
                )
            )

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
        """Connect block signals; this static welcome card currently has none."""
        pass

    @property
    def recent_files_wrapper(self) -> VerticalLayoutWrapper:
        """Return the recent-files wrapper."""
        return self.ui.recent_files_wrapper

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh icons for recent-file display rows."""
        lay = self.ui.recent_files_wrapper.get_layout()
        for index in range(lay.count()):
            item = lay.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, File):
                widget.apply_theme_icons(theme)


__all__ = ["StartRecentBlock"]
