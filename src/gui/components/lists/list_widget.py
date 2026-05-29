"""Styled list widget component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QWidget,
)

from gui.colors import Theme
from gui.components.base.component import Component
from gui.settings import Settings


class List(QListWidget, Component):

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the list widget."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the list widget."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        items: list[str | QListWidgetItem] = [],
        minimum_width: int = 180,
        minimum_height: int = 150,
        selection_mode: QAbstractItemView.SelectionMode = QAbstractItemView.SelectionMode.SingleSelection,
        selection_behavior: QAbstractItemView.SelectionBehavior = QAbstractItemView.SelectionBehavior.SelectItems,
        edit_triggers: QAbstractItemView.EditTrigger = QAbstractItemView.EditTrigger.NoEditTriggers,
        item_alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignVCenter
        | Qt.AlignmentFlag.AlignLeft,
    ):
        """Create a styled list with initial items and interaction policies.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            items: Initial row contents as strings or items.
            minimum_width: Minimum widget width in pixels.
            minimum_height: Minimum widget height in pixels.
            selection_mode: Qt selection mode for the view.
            selection_behavior: Row vs item selection behavior.
            edit_triggers: Which user actions may start editing.
            item_alignment: Default alignment for new text items.
        """
        super().__init__(parent)
        self.texts = List.Text()
        self.setProperty("list", True)
        for item in items:
            self.addItem(item)
        self.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )
        self.setMinimumWidth(minimum_width)
        self.setMinimumHeight(minimum_height)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSelectionMode(selection_mode)
        self.setSelectionBehavior(selection_behavior)
        self.setEditTriggers(edit_triggers)
        self.setItemAlignment(item_alignment)
        self.setAlternatingRowColors(False)

        self.ui = List.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setBaseSize(QSize(Settings.LIST.BASE_WIDTH, Settings.LIST.BASE_HEIGHT))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setSizeAdjustPolicy(QListWidget.SizeAdjustPolicy.AdjustToContents)

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def add_items(self, items: list[QListWidgetItem | str]):
        """Append multiple items, accepting raw strings or concrete items.

        Args:
            items: Iterable of strings or ``QListWidgetItem`` instances.
        """
        for item in items:
            if isinstance(item, str):
                self.addItem(item)
            else:
                self.addItem(item)

    def iter_items(self) -> Iterator[QListWidgetItem]:
        """Iterate over the items in the list."""
        for i in range(self.count()):
            yield self.item(i)

    def is_empty(self) -> bool:
        """Check if the list is empty."""
        return self.count() == 0
