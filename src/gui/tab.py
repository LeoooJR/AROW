from dataclasses import dataclass
from typing import Final

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTabWidget, QWidget

from gui.icons import GenericIcons
from gui.map import MapPanel


class Tab(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Tab labels and related copy for the tab frame."""

        map_tab: Final[str] = "Map"

    @dataclass
    class UI:
        """Widgets that make up the tabbed map area."""

        tabs: QTabWidget
        map_panel: MapPanel

    def __init__(self, parent: QWidget = None):
        """Build the tab widget with a single Map tab.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """

        super().__init__(parent)

        self.texts = Tab.Text()
        self.ui: Tab.UI

        self.setObjectName("tab")
        self.setProperty("tab", True)
        self.setProperty("panel", True)

        layout = QHBoxLayout()

        tabs = QTabWidget()

        tabs.setTabPosition(QTabWidget.TabPosition.North)

        tabs.setMovable(False)

        map_panel = MapPanel(self)

        tabs.addTab(map_panel, self.texts.map_tab)

        tabs.setTabIcon(0, QIcon(GenericIcons.MAP.value))

        layout.addWidget(tabs, 1)

        self.setLayout(layout)
        self.ui = Tab.UI(tabs=tabs, map_panel=map_panel)
