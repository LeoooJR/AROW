from dataclasses import dataclass

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTabWidget, QWidget

from gui.icons import GenericIcons
from gui.map import MapPanel


class Tab(QFrame):

    @dataclass(frozen=True)
    class Text:
        map_tab: str = "Map"

    @dataclass
    class UI:
        tabs: QTabWidget
        map_panel: MapPanel

    def __init__(self, parent: QWidget = None):

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
