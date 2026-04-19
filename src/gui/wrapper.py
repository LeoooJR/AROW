from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget


class VerticalLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on this wrapper."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on this wrapper."""

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
        """Lay out one or more widgets in a vertical column.

        Args:
            parent: Qt parent for this frame.
            widgets: Single widget or list of widgets to stack vertically.
            spacing: Pixels between consecutive widgets.
            margins: Layout contents margins (left, top, right, bottom).
            stretch_at_beginning: When True, insert a stretch before the widgets.
            stretch_at_end: When True, insert a stretch after the widgets.
        """

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
        """Append a widget to the bottom of the vertical layout.

        Args:
            widget: Child widget to add.
        """
        self.layout().addWidget(widget)

    def get_layout(self) -> QVBoxLayout:
        return self.layout()

    def get_widgets(self) -> list[QWidget]:
        return [self.layout().itemAt(i).widget() for i in range(self.layout().count())]


class HorizontalLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on this wrapper."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on this wrapper."""

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
        """Lay out one or more widgets in a horizontal row.

        Args:
            parent: Qt parent for this frame.
            widgets: Single widget or list of widgets to place left-to-right.
            spacing: Pixels between consecutive widgets.
            margins: Layout contents margins (left, top, right, bottom).
            stretch_at_beginning: When True, insert a stretch before the widgets.
            stretch_at_end: When True, insert a stretch after the widgets.
        """

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
        """Append a widget to the right end of the horizontal layout.

        Args:
            widget: Child widget to add.
        """
        self.layout().addWidget(widget)

    def get_layout(self) -> QHBoxLayout:
        return self.layout()

    def get_widgets(self) -> list[QWidget]:
        return [self.layout().itemAt(i).widget() for i in range(self.layout().count())]


class GridLayoutWrapper(QFrame):

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on this wrapper."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on this wrapper."""

        pass

    def __init__(
        self,
        parent: QWidget,
        widgets: QWidget | list[(QWidget, int, int)] = [],
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
    ):
        """Lay out widgets on a grid with optional per-cell alignment.

        Args:
            parent: Qt parent for this frame.
            widgets: Single widget or list of (widget, row, column) tuples.
            spacing: Pixels between grid cells.
            margins: Layout contents margins (left, top, right, bottom).
            alignment: Alignment flag applied when adding each widget to the grid.
        """

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
        """Place a widget at the given grid cell.

        Args:
            widget: Child widget to add.
            row: Zero-based grid row.
            column: Zero-based grid column.
            alignment: Alignment within the cell.
        """
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
