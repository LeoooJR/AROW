from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget


class VerticalLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        pass

    @dataclass
    class UI:
        pass

    def __init__(
        self,
        parent: QWidget,
        widgets: QWidget | list[QWidget] = [],
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
        stretch_at_beginning: bool = False,
        stretch_at_end: bool = False,
    ):

        super().__init__(parent)

        self.texts = VerticalLayoutWrapper.Text()
        self.ui = VerticalLayoutWrapper.UI()

        self.setProperty("vertical-layout-wrapper", True)
        layout = QVBoxLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)

        if stretch_at_beginning:
            layout.addStretch()

        if isinstance(widgets, list):
            for widget in widgets:
                layout.addWidget(widget)
        else:
            layout.addWidget(widgets)

        if stretch_at_end:
            layout.addStretch()

        self.setLayout(layout)

    def add_widget(self, widget: QWidget):
        self.layout().addWidget(widget)

    def get_layout(self) -> QVBoxLayout:
        return self.layout()

    def get_widgets(self) -> list[QWidget]:
        return [self.layout().itemAt(i).widget() for i in range(self.layout().count())]


class HorizontalLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        pass

    @dataclass
    class UI:
        pass

    def __init__(
        self,
        parent: QWidget,
        widgets: QWidget | list[QWidget] = [],
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
        stretch_at_beginning: bool = False,
        stretch_at_end: bool = False,
    ):

        super().__init__(parent)

        self.texts = HorizontalLayoutWrapper.Text()
        self.ui = HorizontalLayoutWrapper.UI()

        self.setProperty("horizontal-layout-wrapper", True)
        layout = QHBoxLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)

        if stretch_at_beginning:
            layout.addStretch()

        if isinstance(widgets, list):
            for widget in widgets:
                layout.addWidget(widget)
        else:
            layout.addWidget(widgets)

        if stretch_at_end:
            layout.addStretch()

        self.setLayout(layout)

    def add_widget(self, widget: QWidget):
        self.layout().addWidget(widget)

    def get_layout(self) -> QHBoxLayout:
        return self.layout()

    def get_widgets(self) -> list[QWidget]:
        return [self.layout().itemAt(i).widget() for i in range(self.layout().count())]


class GridLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        pass

    @dataclass
    class UI:
        pass

    def __init__(
        self,
        parent: QWidget,
        widgets: QWidget | list[(QWidget, int, int)] = [],
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ):

        super().__init__(parent)

        self.texts = GridLayoutWrapper.Text()
        self.ui = GridLayoutWrapper.UI()

        self.setProperty("grid-layout-wrapper", True)
        layout = QGridLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)

        if isinstance(widgets, list):
            for widget, row, column in widgets:
                layout.addWidget(widget, row, column, alignment=alignment)
        else:
            layout.addWidget(widgets)

        self.setLayout(layout)

    def add_widget(
        self,
        widget: QWidget,
        row: int,
        column: int,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ):
        self.layout().addWidget(widget, row, column, alignment=alignment)

    def get_layout(self) -> QGridLayout:
        return self.layout()

    def get_widgets(self) -> list[(QWidget, int, int)]:
        return [
            (
                self.layout().itemAt(i).widget(),
                self.layout().row(i),
                self.layout().column(i),
            )
            for i in range(self.layout().count())
        ]
