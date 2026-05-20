"""
This file contains the generic graphical elements used in the application.
"""

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Final, Iterator

from loguru import logger
from PySide6.QtCore import (
    QAbstractAnimation,
    QDir,
    QEasingCurve,
    QElapsedTimer,
    QObject,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QIntValidator,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QShowEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from gui.animation import apply_highlight_level, compute_sine_pulse_level
from gui.colors import Theme, get_current_palette
from gui.icons import (
    ApplicationIcons,
    GenericIcons,
    OperatingSystemIcons,
    icon_qt_path,
    icon_qt_path_for_theme,
)
from gui.settings import Settings
from gui.signals import view_signals
from gui.svg import get_svg_size
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class QtABCMeta(type(QObject), ABCMeta):
    """Merges QObject's metaclass with abc.ABCMeta so Qt widgets can inherit from Component."""

    pass


class Component(ABC, metaclass=QtABCMeta):
    """
    Abstract base for all graphical components in this module.
    """

    def _finalize_ui_hooks(self) -> None:
        """Run the standard UI hook sequence after widget construction."""
        self._set_size_policy()
        self._set_alignment()
        self._connect_signals()

    @abstractmethod
    def _set_size_policy(self) -> None:
        """Set the size policy for elements composing the widget."""
        ...

    @abstractmethod
    def _set_alignment(self) -> None:
        """Set the alignment for elements composing the widget."""
        ...

    @abstractmethod
    def _connect_signals(self) -> None:
        """Connect signals for elements composing the widget."""
        ...

    @abstractmethod
    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme icons to elements composing the widget."""
        ...


class LeadingIconLabel(QWidget, Component):
    """
    Widget that displays a leading icon and a label.
    """

    @dataclass(frozen=True)
    class Text:
        """Optional plain-text snapshot when the text is a string."""

        text: str | None = None

    @dataclass
    class UI:
        """Widgets composing the leading icon label."""

        svg: SVG
        text: QLabel

    def __init__(
        self,
        parent: QWidget | None,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
        text: str | QLabel,
        font_weight: QFont.Weight = QFont.Weight.Normal,
        spacing: int = 0,
        margins: tuple = (0, 0, 0, 0),
    ):
        """Lay out a leading SVG icon beside a string or external ``QLabel``.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons.
            text: Caption string or pre-built text widget.
            font_weight: Font weight applied when ``text`` is a string.
            spacing: Pixels between icon and text.
            margins: Outer layout margins (left, top, right, bottom).
        """
        # Initialize parent QWidget
        super().__init__(parent)

        self.setObjectName("leading-icon-label")

        self.texts = LeadingIconLabel.Text(text=text if isinstance(text, str) else None)

        if icon is None:
            raise ValueError("icon cannot be None")
        if not isinstance(icon, GenericIcons | OperatingSystemIcons | ApplicationIcons):
            raise ValueError(
                "icon must be a GenericIcons | OperatingSystemIcons | ApplicationIcons"
            )

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons = icon

        layout = QHBoxLayout()
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)  # Spacing between icon and text

        svg = SVG(icon_qt_path(self._icon), self)
        svg.setObjectName("leading-icon")
        svg.setFixedSize(
            get_svg_size(Settings.FONT.SIZE_DEFAULT)
        )  # Set the size of the leading icon depending on the font size

        layout.addWidget(svg)

        if isinstance(text, str):
            label = QLabel(text, self)
        else:
            label = text
        label.setObjectName("label")
        label.setFont(
            QFont(
                Settings.FONT.FAMILY,
                Settings.FONT.SIZE_DEFAULT,
                QFont.Weight.Normal,
            )
        )

        layout.addWidget(label)

        self.setLayout(layout)

        self.ui: LeadingIconLabel.UI = LeadingIconLabel.UI(svg=svg, text=label)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        """Set the size policy for elements composing the leading icon label."""
        self.ui.svg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _set_alignment(self) -> None:
        """Set the alignment for elements composing the leading icon label."""
        self.ui.svg.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.layout().setAlignment(
            self.ui.svg, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.ui.text.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )
        self.layout().setAlignment(
            self.ui.text, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
        )

    def _connect_signals(self) -> None:
        """Connect signals for elements composing the leading icon label."""
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Apply theme icons to elements composing the leading icon label."""
        self.ui.svg.set_path(icon_qt_path_for_theme(theme, self._icon))

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons
    ) -> None:
        """Set the leading icon path.

        Args:
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons.
        """
        if icon is None:
            return
        if not isinstance(icon, GenericIcons | OperatingSystemIcons | ApplicationIcons):
            raise ValueError(
                "icon must be a GenericIcons | OperatingSystemIcons | ApplicationIcons"
            )
        self._icon = icon
        self.ui.svg.set_path(icon_qt_path(self._icon))

    def set_text(self, text: QLabel | str | None = None) -> None:
        """Set the text of the leading icon label.

        Args:
            text: Text string or pre-built text widget.
        """
        if text is None:
            return
        if isinstance(text, str):
            self.texts = LeadingIconLabel.Text(text=text)
            self.ui.text.setText(text)
            return

        layout = self.layout()
        layout.removeWidget(self.ui.text)
        self.ui.text.deleteLater()

        text.setParent(self)
        text.setObjectName("label")
        layout.addWidget(text)
        self.ui.text = text
        self.texts = LeadingIconLabel.Text(text=None)
        self._finalize_ui_hooks()


class PanelTitle(QFrame, Component):
    """
    Widget that displays a panel title.
    """

    @dataclass(frozen=True)
    class Text:
        """Title string used for styling and dataclass symmetry."""

        title: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the title row."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        text="",
        font_size=24,
        font_weight=QFont.Weight.DemiBold,
        icon_path=None,
        icon_size=None,
    ):
        """Build a horizontal title with optional leading icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Title string.
            font_size: Point size for the title label.
            font_weight: Qt font weight for the title label.
            icon_path: Optional SVG path; omitted hides the icon.
            icon_size: Fixed icon size; derived from font when omitted.
        """
        super().__init__(parent)
        self.texts = PanelTitle.Text(title=text)
        self.ui = PanelTitle.UI()

        self.setProperty("panel-title", True)

        # Calculate icon size based on font size if not provided (icon should be ~1.3x font size for good visual balance)
        if icon_size is None:
            icon_size = get_svg_size(font_size)

        layout = QHBoxLayout()
        # Add padding for better visual spacing within panels
        layout.setContentsMargins(
            Settings.PANEL.TITLE_PADDING_LEFT,
            Settings.PANEL.TITLE_PADDING_TOP,
            Settings.PANEL.TITLE_PADDING_RIGHT,
            Settings.PANEL.TITLE_PADDING_BOTTOM,
        )
        layout.setSpacing(
            Settings.PANEL.TITLE_ICON_SPACING
        )  # Increased spacing for better visual separation

        self._leading_svg: SVG | None = None
        if icon_path is not None:
            self._leading_svg = SVG(icon_path, self)
            self._leading_svg.setFixedSize(icon_size)
            self._leading_svg.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
            )
            layout.addWidget(self._leading_svg)

        label = QLabel(text, self)
        label.setProperty("section-title", True)
        label.setFont(QFont(Settings.FONT.FAMILY, font_size, font_weight))
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label)

        self.setLayout(layout)
        self.setMaximumSize(layout.sizeHint())
        self._finalize_ui_hooks()

    def set_leading_icon_path(self, path: str) -> None:
        """Swap the title-leading SVG resource (e.g. after a light/dark theme change)."""
        if self._leading_svg is not None:
            self._leading_svg.set_path(path)

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class Button(QPushButton, Component):

    @dataclass(frozen=True)
    class Text:
        """Primary action label for the button."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the button."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        text: str,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
    ):
        """Create a styled primary button with optional icon.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Button label text.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown before the label.
        """
        if icon is not None:
            super().__init__(QIcon(icon_qt_path(icon)), text, parent)
            self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
            self._icon = icon
        else:
            super().__init__(text, parent)
            self._icon = None

        self.setProperty("button", True)

        self.texts = Button.Text(label=text)

        self.ui = Button.UI()

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setFixedHeight(Settings.DIMENSION.BUTTON_HEIGHT)
        # Set minimum width based on content, but allow horizontal expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path_for_theme(theme, self._icon)))


class WalkthroughButton(QPushButton, Component):
    """
    Welcome walkthrough row styled as a large, soft card: lead icon (left, vertically centered),
    helper-colored text, small hand-index-style icon pinned to the top-right.
    Uses an internal layout (not QPushButton text/icon) so spacing matches the design reference.
    """

    @dataclass(frozen=True)
    class Text:
        """Walkthrough row label text."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the walkthrough button."""

        leading_svg: SVG
        label: QLabel
        trailing_svg: SVG

    def __init__(
        self,
        parent: QWidget | None,
        text: str,
        leading_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
        trailing_icon: GenericIcons | OperatingSystemIcons | ApplicationIcons,
    ):
        """Build the custom walkthrough card button layout.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Main descriptive label (word-wrapped).
            leading_icon: Left column SVG asset.
            trailing_icon: Top-right hint SVG asset.
        """
        super().__init__(parent)

        self.texts = WalkthroughButton.Text(label=text)

        self.setObjectName("welcome-walkthrough-button")
        self.setProperty("welcome-walkthrough-button", True)

        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        pad_h = Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_PADDING_H
        pad_v = Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_PADDING_V
        row = QHBoxLayout(self)
        row.setContentsMargins(pad_h, pad_v, pad_h, pad_v)
        row.setSpacing(Settings.SPACING.SM)

        self._leading_icon = leading_icon
        lead_px = get_svg_size(Settings.FONT.SIZE_HELPER)
        leading_svg = SVG(icon_qt_path(leading_icon), self)
        leading_svg.setObjectName("walkthrough-card-lead-icon")
        leading_svg.setFixedSize(lead_px)

        label = QLabel(text, self)
        label.setObjectName("walkthrough-card-label")
        label.setWordWrap(True)

        trailing_host = QWidget(self)
        trailing_host.setObjectName("walkthrough-card-trailing")
        trailing_col = QVBoxLayout(trailing_host)
        trailing_col.setContentsMargins(0, 0, 0, 0)
        trailing_col.setSpacing(0)

        self._trailing_icon = trailing_icon
        trail_px = max(get_svg_size(Settings.FONT.SIZE_HELPER).width(), 20)
        trailing_svg = SVG(icon_qt_path(trailing_icon), self)
        trailing_svg.setObjectName("walkthrough-card-trail-icon")
        trailing_svg.setFixedSize(trail_px, trail_px)

        trailing_col.addWidget(
            trailing_svg, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        trailing_col.addStretch(1)

        row.addWidget(leading_svg, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label, 1)
        row.addWidget(
            trailing_host, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

        self.ui = WalkthroughButton.UI(
            leading_svg=leading_svg, label=label, trailing_svg=trailing_svg
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setMinimumHeight(Settings.DIMENSION.WELCOME_WALKTHROUGH_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        self.ui.leading_svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.ui.trailing_svg.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        """Refresh walkthrough row SVGs for the given palette."""
        self.ui.leading_svg.set_path(icon_qt_path_for_theme(theme, self._leading_icon))
        self.ui.trailing_svg.set_path(
            icon_qt_path_for_theme(theme, self._trailing_icon)
        )


class ToolButton(QToolButton, Component):

    @dataclass(frozen=True)
    class Text:
        """Tooltip copy associated with the tool button."""

        tooltip: str | None = None

    @dataclass
    class UI:
        """Reserved for future explicit child references on the tool button."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
        tooltip: str | None = None,
    ):
        """Create a compact icon button with optional tooltip.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
            tooltip: Hover tooltip string.
        """
        super().__init__(parent)

        self.setProperty("tool-button", True)

        self.texts = ToolButton.Text(tooltip=tooltip)

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path(self._icon)))
            self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if tooltip is not None:
                self.setToolTip(tooltip)

        self.ui = ToolButton.UI()

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setFixedHeight(Settings.DIMENSION.TOOLBUTTON_HEIGHT)
        self.setFixedWidth(self.sizeHint().width())

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        if self._icon is not None:
            self.setIcon(QIcon(icon_qt_path_for_theme(theme, self._icon)))

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None
    ):
        """Apply a new icon and optional size to the tool button.

        Args:
            icon: GenericIcons | OperatingSystemIcons | ApplicationIcons for the button face.
        """
        if icon is None:
            return

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon
        self.setIcon(QIcon(icon_qt_path(self._icon)))
        self.setIconSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))


class SelectionField(QComboBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Placeholder string for the non-editable combo field."""

        placeholder: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the selection field."""

        pass

    def __init__(self, parent: QWidget | None, placeholder: str):
        """Configure a styled combo box with placeholder text.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            placeholder: Shown when no item is selected meaningfully.
        """

        super().__init__(parent)

        self.texts = SelectionField.Text(placeholder=placeholder)

        self.setProperty("selection-field", True)
        self.setEditable(False)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.setInsertPolicy(QComboBox.InsertPolicy.InsertAlphabetically)
        self.setMinimumWidth(Settings.COMBOBOX.MIN_WIDTH)
        self.setMinimumHeight(Settings.COMBOBOX.MIN_HEIGHT)
        self.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.Normal)
        )

        self.setPlaceholderText(placeholder)
        self.setCurrentIndex(0)

        self.ui = SelectionField.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class DemiBoldText(QLabel, Component):

    @dataclass(frozen=True)
    class Text:
        """Demi-bold label content."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on demi-bold text."""

        pass

    def __init__(self, parent: QWidget | None, text: str):
        """Create a demi-bold emphasis label.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Label string.
        """
        super().__init__(text, parent)
        self.texts = DemiBoldText.Text(label=text)

        self.setProperty("demi-bold-text", True)
        self.setFont(
            QFont(
                Settings.FONT.FAMILY, Settings.FONT.SIZE_DEFAULT, QFont.Weight.DemiBold
            )
        )
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        self.ui = DemiBoldText.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class HelperText(QLabel, Component):

    @dataclass(frozen=True)
    class Text:
        """Helper or secondary caption text."""

        label: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on helper text."""

        pass

    def __init__(self, parent: QWidget | None, text: str):
        """Create smaller helper-colored explanatory text.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Helper string.
        """

        super().__init__(text, parent)
        self.texts = HelperText.Text(label=text)

        self.setProperty("helper-text", True)
        self.setFont(
            QFont(Settings.FONT.FAMILY, Settings.FONT.SIZE_HELPER, QFont.Weight.Normal)
        )
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        self.ui = HelperText.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


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
        self.setAlternatingRowColors(True)

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


########################################################################################################################
# ELEMENTS RELATED TO THE SVG
########################################################################################################################


class SVG(QLabel, Component):
    """Custom QLabel that renders SVG using QSvgRenderer"""

    path: str

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the SVG label."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the SVG label."""

        pass

    def __init__(self, svg_path: str, parent: QWidget | None = None):
        """Load an SVG from disk and paint it in ``paintEvent``.

        Args:
            svg_path: Filesystem path to the SVG asset.
            parent: Optional Qt parent widget for lifetime and hierarchy.
        """
        super().__init__(parent)
        self.texts = SVG.Text()
        self.setProperty("svg", True)
        self.path = svg_path
        self.renderer: QSvgRenderer | None = None
        self.set_path(svg_path)

        self.ui = SVG.UI()
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.renderer is not None:
            try:
                self.renderer.render(painter)
            except Exception as e:
                print(f"Error rendering SVG using QSvgRenderer: {e}")
        painter.end()

    def set_path(self, path: str):
        """Replace the SVG source and refresh rendering.

        Args:
            path: New filesystem path to an SVG asset.
        """
        self.path = path
        try:
            self.renderer = QSvgRenderer(self.path)
        except Exception as e:
            print(f"Error creating SVG renderer: {e}")
            self.renderer = None
        self.update()


class PlaceHolder(QFrame, Component):
    """
    Empty-state placeholder: optional SVG on top, then centered text.
    Text uses a softer color (PLACEHOLDER_TEXT). Use icon_path to show an icon above the label.
    """

    @dataclass(frozen=True)
    class Text:
        """Optional plain-text snapshot when the body is a string."""

        text: str | None = None

    @dataclass
    class UI:
        """Primary text label and optional top icon."""

        text: QLabel
        svg: SVG

    def __init__(
        self,
        parent: QWidget | None,
        text: QLabel | str,
        minimum_width: int = 180,
        minimum_height: int = 150,
        stretch_widgets: bool = False,
        icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None,
    ):
        """Build a vertically centered empty-state block.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            text: Centered message as string or external label widget.
            minimum_width: Minimum width before default placeholder sizing applies.
            minimum_height: Minimum height before default placeholder sizing applies.
            stretch_widgets: Layout stretch factor for the text row when True.
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown above the text.
        """
        super().__init__(parent)
        self.texts = PlaceHolder.Text(text=text if isinstance(text, str) else None)
        self.ui: PlaceHolder.UI

        self.setProperty("place-holder", True)

        layout = QVBoxLayout()
        layout.setContentsMargins(
            Settings.PLACEHOLDER.PADDING,
            Settings.PLACEHOLDER.PADDING,
            Settings.PLACEHOLDER.PADDING,
            Settings.PLACEHOLDER.PADDING,
        )
        layout.setSpacing(Settings.PLACEHOLDER.SPACING)

        self.setMinimumWidth(
            minimum_width if minimum_width != 180 else Settings.PLACEHOLDER.MIN_WIDTH
        )
        self.setMinimumHeight(
            minimum_height if minimum_height != 150 else Settings.PLACEHOLDER.MIN_HEIGHT
        )

        layout.addStretch()

        if icon is not None:
            self._icon: (
                GenericIcons | OperatingSystemIcons | ApplicationIcons | None
            ) = icon
            icon_size = Settings.PLACEHOLDER.ICON_SIZE
            svg = SVG(icon_qt_path(icon), self)
            svg.setFixedSize(icon_size, icon_size)
            svg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(svg)

        if isinstance(text, str):
            label = QLabel(text, self)
        else:
            label = text

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label, int(stretch_widgets))

        layout.addStretch()
        self.setLayout(layout)

        self.ui = PlaceHolder.UI(text=label, svg=svg)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        self.layout().setAlignment(self.ui.text, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(self.ui.svg, Qt.AlignmentFlag.AlignCenter)

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        if self._icon is not None:
            self.ui.svg.set_path(icon_qt_path_for_theme(theme, self._icon))

    def set_text(self, text: str) -> None:
        """Update the placeholder message.

        Args:
            text: New body string for the label.
        """
        self.ui.text.setText(text)

    def set_icon(
        self, icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = None
    ) -> None:
        """Swap the illustration above the text.

        Args:
            icon: Optional GenericIcons | OperatingSystemIcons | ApplicationIcons shown above the text.
        """
        if icon is None:
            return

        self._icon: GenericIcons | OperatingSystemIcons | ApplicationIcons | None = icon
        self.ui.svg.set_path(icon_qt_path(self._icon))


class FileOpenDialog(QFileDialog, Component):

    @dataclass(frozen=True)
    class Text:
        """Default window title and name filter for spreadsheet open."""

        window_title: Final[str] = "Open a file"
        name_filter: Final[str] = "Tablesheet files (*.xlsx, *.xls, *.csv)"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the open dialog."""

        pass

    def __init__(self, parent: QWidget = None):
        """Configure a read-only open dialog for tabular files.

        Args:
            parent: Optional parent window for modality placement.
        """

        super().__init__(parent)
        self.texts = FileOpenDialog.Text()
        self.ui = FileOpenDialog.UI()

        self.setWindowTitle(self.texts.window_title)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        self.setFileMode(QFileDialog.FileMode.ExistingFile)
        self.setNameFilter(self.texts.name_filter)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setFilter(QDir.Filter.Files | QDir.Filter.Readable)
        self.setOptions(
            QFileDialog.Option.ReadOnly | QFileDialog.Option.DontUseCustomDirectoryIcons
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class FileSaveDialog(QFileDialog, Component):

    @dataclass(frozen=True)
    class Text:
        """Default window title, filter, and suffix for log save."""

        window_title: Final[str] = "Save a file"
        name_filter: Final[str] = "Plain text files (*.log)"
        default_suffix: Final[str] = "log"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the save dialog."""

        pass

    def __init__(self, parent: QWidget = None):
        """Configure a save dialog targeting plain log files.

        Args:
            parent: Optional parent window for modality placement.
        """

        super().__init__(parent)
        self.texts = FileSaveDialog.Text()
        self.ui = FileSaveDialog.UI()

        self.setWindowTitle(self.texts.window_title)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setNameFilter(self.texts.name_filter)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setFilter(QDir.Filter.Files | QDir.Filter.Readable)
        self.setOptions(QFileDialog.Option.DontUseCustomDirectoryIcons)
        self.setDefaultSuffix(self.texts.default_suffix)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class WarningDialog(QMessageBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Primary, detailed, and informative strings for the warning box."""

        title: str = ""
        text: str = ""
        detailed_text: str = ""
        informative_text: Final[str] = (
            "This software is for experimental purposes. Use at your own risk."
        )

    @dataclass
    class UI:
        """Reserved for future explicit child references on the warning dialog."""

        pass

    def __init__(self, parent: QWidget = None, title=str, text=str, detailed_text=str):
        """Show a warning message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self.texts = WarningDialog.Text(
            title=title,
            text=text,
            detailed_text=detailed_text,
        )
        self.ui = WarningDialog.UI()

        self.setWindowTitle(self.texts.title)
        self.setText(self.texts.text)
        self.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        self.setDetailedText(self.texts.detailed_text)
        self.setInformativeText(self.texts.informative_text)
        self.setIcon(QMessageBox.Icon.Warning)

        for label in self.findChildren(QLabel):
            if label.text() == self.informativeText():
                label.setProperty("messagebox-informative-text", True)
            elif label.text() == self.detailedText():
                label.setProperty("messagebox-detailed-text", True)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class QuestionDialog(QMessageBox, Component):

    @dataclass(frozen=True)
    class Text:
        """Primary, detailed, and informative strings for the question box."""

        title: str = ""
        text: str = ""
        detailed_text: str = ""
        informative_text: Final[str] = (
            "This software is for experimental purposes. Use at your own risk."
        )

    @dataclass
    class UI:
        """Reserved for future explicit child references on the question dialog."""

        pass

    def __init__(self, parent: QWidget = None, title=str, text=str, detailed_text=str):
        """Show a question message with Yes/Cancel actions.

        Args:
            parent: Optional parent window for modality placement.
            title: Window title string.
            text: Primary message body.
            detailed_text: Expanded explanation shown in the details area.
        """

        super().__init__(parent)
        self.texts = QuestionDialog.Text(
            title=title,
            text=text,
            detailed_text=detailed_text,
        )
        self.ui = QuestionDialog.UI()

        self.setWindowTitle(self.texts.title)
        self.setText(self.texts.text)
        self.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        self.setDetailedText(self.texts.detailed_text)
        self.setInformativeText(self.texts.informative_text)
        self.setIcon(QMessageBox.Icon.Question)

        for label in self.findChildren(QLabel):
            if label.text() == self.informativeText():
                label.setProperty("messagebox-informative-text", True)
            elif label.text() == self.detailedText():
                label.setProperty("messagebox-detailed-text", True)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class Toast(QWidget, Component):

    @dataclass(frozen=True)
    class Text:
        """Toast body and severity level token."""

        message: str = ""
        level: str = "info"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the toast."""

        pass

    def __init__(
        self, parent: QWidget, message: str, level: str = "info", duration: int = 3000
    ):
        """Create a short-lived top-level toast (parent is ignored for window flags).

        Args:
            parent: Logical owner used only for context; toast is top-level.
            message: Body text shown in the banner.
            level: Visual style token such as info, success, warning, or error.
            duration: Auto-close delay in milliseconds.
        """
        # Ignore parent completely - create as completely independent top-level window
        # This prevents any layout interference with parent widgets
        super().__init__(None)
        self.texts = Toast.Text(message=message, level=level)
        self.ui = Toast.UI()

        # Set window flags BEFORE any other operations
        # Using Dialog flag for better cross-platform behavior
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Set attributes for better display
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        # Set main widget styling (transparent to show shadow)
        self.setObjectName("toast")
        palette = get_current_palette()
        self.setStyleSheet(f"""
            QWidget#toast {{
                background-color: {palette.TRANSPARENT};
            }}
        """)

        # Create label with proper styling
        label = QLabel(message, self)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setWordWrap(True)

        # Create inner container for content (needed to combine shadow and opacity effects)
        inner_widget = QWidget(self)
        inner_widget.setObjectName("toast-inner")

        if level == "info":
            color = palette.PRIMARY
            icon_path = icon_qt_path(GenericIcons.INFO)
        elif level == "success":
            color = palette.SUCCESS
            icon_path = icon_qt_path(GenericIcons.CHECK)
        elif level == "warning":
            color = palette.WARNING
            icon_path = icon_qt_path(GenericIcons.EXCLAMATION)
        elif level == "error":
            color = palette.ERROR
            icon_path = icon_qt_path(GenericIcons.X_CIRCLE)

        inner_widget.setStyleSheet(f"""
            QWidget#toast-inner {{
                background-color: {palette.WHITE};
                border: 1px solid {palette.LIGHT_DIVIDER};
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
            QLabel {{
                color: {palette.BLACK};
                background-color: {palette.TRANSPARENT};
                font-family: "{Settings.FONT.FAMILY}";
                font-size: {Settings.FONT.SIZE_DEFAULT}px;
                font-weight: {Settings.FONT.WEIGHT_NORMAL};
                padding: 0px;
                margin: 0px;
            }}
        """)

        inner_layout = QHBoxLayout(inner_widget)
        inner_layout.setContentsMargins(*Settings.SPACING.MARGIN_TOAST)
        inner_layout.setSpacing(Settings.SPACING.ICON_SPACING)

        svg = SVG(icon_path, inner_widget)
        svg.setFixedSize(get_svg_size(label.font().pointSize()))
        svg.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        inner_layout.addWidget(svg)
        inner_layout.addWidget(label, 1)

        # Set main widget layout to contain inner widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(inner_widget)

        # Set minimum and maximum size for better appearance
        self.setMinimumWidth(Settings.DIMENSION.TOAST_MIN_WIDTH)
        self.setMaximumWidth(Settings.DIMENSION.TOAST_MAX_WIDTH)
        self.adjustSize()

        # Position the window
        self._move_to_bottom_right()

        # Add shadow effect to main widget for modern appearance
        shadow_effect = QGraphicsDropShadowEffect(self)
        shadow_effect.setBlurRadius(Settings.SHADOW.BLUR_RADIUS)
        shadow_effect.setXOffset(Settings.SHADOW.X_OFFSET)
        shadow_effect.setYOffset(Settings.SHADOW.Y_OFFSET)
        shadow_effect.setColor(
            QColor(*Settings.SHADOW.COLOR_RGBA)
        )  # Subtle black shadow with transparency
        self.setGraphicsEffect(shadow_effect)

        # Add opacity effect to inner widget for fade animation
        self._opacity_effect = QGraphicsOpacityEffect(inner_widget)
        inner_widget.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)

        # Show the window
        self.show()
        self.raise_()

        # Fade in animation
        self._fade_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in.setDuration(Settings.ANIMATION.TOAST_FADE_IN_DURATION)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

        # Auto-close after duration (owned timer to stop safely on teardown)
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.close)
        self._auto_close_timer.start(duration)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _move_to_bottom_right(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            offset = Settings.DIMENSION.TOAST_OFFSET
            x = geo.right() - self.width() - offset
            y = geo.bottom() - self.height() - offset
            self.move(x, y)

    def closeEvent(self, event) -> None:
        """Stop runtime resources before Qt destroys the toast hierarchy."""
        if hasattr(self, "_auto_close_timer") and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
        if (
            hasattr(self, "_fade_in")
            and self._fade_in.state() == QAbstractAnimation.State.Running
        ):
            self._fade_in.stop()
        super().closeEvent(event)


class ProgressBar(QProgressBar, Component):
    """
    Step-based progress bar for pre-simulation steps.
    """

    DEFAULT_STEP_LABELS: list[str] = [
        "Not started",
        "Device selected",
        "Location set",
        "Ready to start",
    ]

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the progress bar."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the progress bar."""

        pass

    def __init__(self, parent: QWidget | None, step_labels: list[str] | None = None):
        """Create a four-step horizontal progress indicator.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            step_labels: Custom labels per step index; defaults to built-in list.
        """
        super().__init__(parent)
        self.texts = ProgressBar.Text()
        self.ui = ProgressBar.UI()
        self.setProperty("progress-bar", True)
        self.setFixedHeight(Settings.DIMENSION.PROGRESSBAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setInvertedAppearance(False)
        self.setMaximum(3)
        self.setMinimum(0)
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setValue(0)
        self.setTextVisible(True)
        self._step_labels: list[str] = (
            step_labels
            if step_labels is not None
            else list(ProgressBar.DEFAULT_STEP_LABELS)
        )
        self._update_format(self.value())
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        self.valueChanged.connect(self._update_format)

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _update_format(self, value: int) -> None:
        if 0 <= value < len(self._step_labels):
            self.setFormat(f"{value}. {self._step_labels[value]}")
        else:
            self.setFormat("%v. Step %v")


class Image(QLabel, Component):
    """
    Label that displays an image.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the image label."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the image label."""

        pass

    def __init__(self, parent: QWidget | None, image_path: str):
        """Load a pixmap from disk and enable scaled contents.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            image_path: Path to the raster image asset.
        """
        super().__init__(parent)
        self.texts = Image.Text()
        self.ui = Image.UI()
        self.setProperty("image", True)
        self.setPixmap(QPixmap(image_path))
        self.setScaledContents(True)
        self._finalize_ui_hooks()

    def set_pixmap_path(self, image_path: str) -> None:
        """Reload the pixmap from a (possibly theme-specific) Qt resource path."""
        self.setPixmap(QPixmap(image_path))

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


class GroupBox(QGroupBox, Component):
    """
    Group box that displays a title and a content area.
    """

    @dataclass(frozen=True)
    class Text:
        """Group title string mirrored for dataclass symmetry."""

        title: str = ""

    @dataclass
    class UI:
        """Reserved for future explicit child references on the group box."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        layout: QVBoxLayout | QHBoxLayout | None = None,
        widgets: list[QWidget] | None = None,
        title: str = "",
    ):
        """Create a titled group with optional pre-built layout and children.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            layout: Inner layout to attach before adding widgets.
            widgets: Optional child widgets appended to the inner layout.
            title: Group box title text.
        """
        super().__init__(parent, title=title, alignment=Qt.AlignmentFlag.AlignLeft)
        self.texts = GroupBox.Text(title=title)
        self.ui = GroupBox.UI()
        self.setProperty("group-box", True)
        self.setFlat(False)
        if layout is not None:
            self.setLayout(layout)
        if widgets is not None:
            for widget in widgets:
                self.layout().addWidget(widget)
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


IndicatorState = str  # "default" | "valid" | "warning" | "error"


class ConditionIndicator(QFrame, Component):
    """
    Small top-right indicator with four states: default (grey), valid (green), warning (orange), error (red).
    Used to show if a condition is met before simulation (e.g. host identity). Visible but soft.
    Pulses (opacity animation) when state is warning or error to catch the user's eye.
    The circle is drawn in paintEvent so it stays round at any size (stylesheet border-radius fails on small widgets).
    Use objectName e.g. "host-identity-indicator" or "condition-indicator"; property "indicator-state" for stylesheet.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the indicator."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the indicator."""

        pass

    def __init__(
        self, parent: QWidget | None = None, object_name: str = "condition-indicator"
    ):
        """Create a small circular state indicator.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            object_name: Qt object name used for stylesheet targeting.
        """
        super().__init__(parent)
        self.texts = ConditionIndicator.Text()
        self.ui = ConditionIndicator.UI()
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        size = Settings.DIMENSION.CONDITION_INDICATOR_SIZE
        self.setFixedSize(size, size)
        self._state: IndicatorState = "default"
        self.set_state(self._state)
        self.setProperty("indicator-state", self._state)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._pulse_group: QSequentialAnimationGroup | None = None
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _indicator_color(self) -> str:
        """Return palette color for current state (for paintEvent)."""
        palette = get_current_palette()
        if self._state == "valid":
            return palette.SUCCESS
        if self._state == "warning":
            return palette.PRIMARY
        if self._state == "error":
            return palette.ERROR
        return palette.HELPER_TEXT  # default

    def paintEvent(self, event):
        """Draw a circle so the indicator stays round at any size (avoids stylesheet border-radius issues)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setBrush(QColor(self._indicator_color()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())
        painter.end()

    def set_state(self, state: IndicatorState) -> None:
        """Set indicator state: 'default' (grey), 'valid' (green), 'warning' (orange), 'error' (red)."""
        if state == self._state:
            return
        self._state = state
        self.setProperty("indicator-state", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        if state in ("warning", "error"):
            self._start_pulse()
        else:
            self._stop_pulse()
            self._opacity_effect.setOpacity(1.0)

    def _start_pulse(self) -> None:
        half = Settings.ANIMATION.INDICATOR_PULSE_DURATION // 2
        easing = QEasingCurve.Type.InOutSine
        out = QPropertyAnimation(self._opacity_effect, b"opacity")
        out.setDuration(half)
        out.setStartValue(1.0)
        out.setEndValue(0.45)
        out.setEasingCurve(easing)
        inc = QPropertyAnimation(self._opacity_effect, b"opacity")
        inc.setDuration(half)
        inc.setStartValue(0.45)
        inc.setEndValue(1.0)
        inc.setEasingCurve(easing)
        if (
            self._pulse_group is not None
            and self._pulse_group.state() == QAbstractAnimation.State.Running
        ):
            self._pulse_group.stop()
        self._pulse_group = QSequentialAnimationGroup(self)
        self._pulse_group.addAnimation(out)
        self._pulse_group.addAnimation(inc)
        self._pulse_group.finished.connect(self._on_pulse_finished)
        self._pulse_group.start()

    def _stop_pulse(self) -> None:
        if self._pulse_group is not None:
            self._pulse_group.finished.disconnect(self._on_pulse_finished)
            if self._pulse_group.state() == QAbstractAnimation.State.Running:
                self._pulse_group.stop()
            self._pulse_group = None

    def _on_pulse_finished(self) -> None:
        if self._state in ("warning", "error") and self._pulse_group is not None:
            self._pulse_group.start()

    def state(self) -> IndicatorState:
        return self._state


class File(QWidget, Component):
    """
    Widget that displays a file (icon, name, format). Styled via stylesheet (file-display, file-icon-wrapper, file-name).
    Filename is elided with ellipsis when too long. Do not add a close button.
    """

    @dataclass(frozen=True)
    class Text:
        """File row labels and save-as tooltip."""

        file_name: str = ""
        file_type: str = ""
        save_as_tooltip: Final[str] = "Save as"

    @dataclass
    class UI:
        """Reserved for future explicit child references on the file row."""

        pass

    def __init__(
        self,
        parent: QWidget | None,
        file_name: str,
        file_type: str,
        file_save: bool = False,
    ):
        """Render a file summary row with optional save-as affordance.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            file_name: Display name for the file.
            file_type: Short type label (e.g. extension category).
            file_save: When True, show a save-as tool button.
        """
        super().__init__(parent)
        self.texts = File.Text(file_name=file_name, file_type=file_type)
        self.ui = File.UI()

        self.setProperty("file", True)
        self.setObjectName("file-display")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._file_name = file_name
        self._file_save = file_save

        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.ICON_SPACING)

        file_icon_wrapper = QWidget(self)
        file_icon_wrapper.setObjectName("file-icon-wrapper")
        file_icon_wrapper.setLayout(QVBoxLayout())
        file_icon_wrapper.layout().setContentsMargins(0, 0, 0, 0)
        file_icon = SVG(icon_qt_path(GenericIcons.FILE), file_icon_wrapper)
        file_icon.setFixedSize(get_svg_size(Settings.FONT.SIZE_DEFAULT))
        file_icon_wrapper.layout().addWidget(file_icon)
        file_icon_wrapper.layout().setAlignment(file_icon, Qt.AlignmentFlag.AlignCenter)
        self._file_icon = file_icon
        layout.addWidget(file_icon_wrapper)
        layout.setAlignment(
            file_icon_wrapper,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        )

        file_description = QWidget(self)
        file_description.setObjectName("file-description")
        file_description.setLayout(QVBoxLayout())
        file_description.layout().setContentsMargins(0, 0, 0, 0)
        file_description.layout().setSpacing(2)
        file_name_label = QLabel(file_name, file_description)
        file_name_label.setObjectName("file-name")
        file_name_label.setWordWrap(False)
        file_description.layout().addWidget(file_name_label)
        file_description.layout().setAlignment(
            file_name_label, Qt.AlignmentFlag.AlignLeft
        )

        file_type_label = HelperText(file_description, file_type.upper())
        file_description.layout().addWidget(file_type_label)
        file_description.layout().setAlignment(
            file_type_label, Qt.AlignmentFlag.AlignLeft
        )
        self._file_description = file_description
        self._file_type_label = file_type_label
        layout.addWidget(file_description, 1)
        layout.setAlignment(
            file_description, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        if self._file_save:
            save_as_button = ToolButton(
                self,
                icon=GenericIcons.SAVE_AS,
                tooltip=self.texts.save_as_tooltip,
            )
            layout.addWidget(save_as_button)
            layout.setAlignment(save_as_button, Qt.AlignmentFlag.AlignRight)
            self._save_as_button = save_as_button

        self._file_name_label = file_name_label
        self.setLayout(layout)
        self._pending_name_elide_update: bool = False
        self._pending_name_elide_retry: bool = False
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        if hasattr(self, "_save_as_button"):
            self._save_as_button.clicked.connect(self._on_save_as_button_clicked)

    def apply_theme_icons(self, theme: Theme) -> None:
        self._file_icon.set_path(icon_qt_path_for_theme(theme, GenericIcons.FILE))
        if hasattr(self, "_save_as_button"):
            self._save_as_button.apply_theme_icons(theme)

    def _on_save_as_button_clicked(self) -> None:
        """Handle the save as button click event."""
        dialog = FileSaveDialog(self)
        if dialog.exec():
            filename: list[str] = dialog.selectedFiles()
            if filename:
                view_signals.SimulationLogFileUpdateRequested.emit(filename[0])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_display()

    def refresh_display(self) -> None:
        """Refresh filename/type layout after parent geometry changes."""
        if not isValid(self):
            return
        if not self._file_name or not self._file_name_label:
            return
        if not isValid(self._file_name_label):
            return

        if self._file_name_label.text() != self._file_name:
            self._file_name_label.setText(self._file_name)

        for widget in (self, self._file_description, self._file_name_label):
            if widget.layout() is not None:
                widget.layout().activate()
            widget.updateGeometry()

        if not self._pending_name_elide_update:
            self._pending_name_elide_update = True
            QTimer.singleShot(0, self._update_file_name_display)

    def _file_name_available_width(self) -> int:
        """Best-effort content width for filename elision."""
        widths: list[int] = []
        if isValid(self._file_name_label):
            widths.append(self._file_name_label.width())
        if isValid(self._file_description):
            widths.append(self._file_description.contentsRect().width())
        positive_widths = [width for width in widths if width > 0]
        return min(positive_widths) if positive_widths else 0

    def _update_file_name_display(self) -> None:
        self._pending_name_elide_update = False
        if not isValid(self):
            return
        if not self._file_name or not self._file_name_label:
            return
        if not isValid(self._file_name_label):
            return

        fm = QFontMetrics(self._file_name_label.font())
        available_w = self._file_name_available_width()
        if (
            available_w <= 0
            or not self.isVisible()
            or not self._file_name_label.isVisible()
        ):
            if self._file_name_label.text() != self._file_name:
                self._file_name_label.setText(self._file_name)
            if (
                self.isVisible()
                and self._file_name_label.isVisible()
                and not self._pending_name_elide_retry
            ):
                self._pending_name_elide_retry = True
                self._pending_name_elide_update = True
                QTimer.singleShot(0, self._update_file_name_display)
            return
        self._pending_name_elide_retry = False

        # Only elide when the full text doesn't fit in the current available width.
        # This preserves short filenames when there is enough space.
        full_text_w = fm.horizontalAdvance(self._file_name)
        fudge_px = Settings.SPACING.XS  # small margin for sub-pixel/font rounding
        if full_text_w <= available_w - fudge_px:
            if self._file_name_label.text() != self._file_name:
                self._file_name_label.setText(self._file_name)
            return

        elided = fm.elidedText(
            self._file_name, Qt.TextElideMode.ElideRight, available_w
        )
        if self._file_name_label.text() != elided:
            self._file_name_label.setText(elided)

    def set_file_display(self, file_name: str, file_type: str) -> None:
        """Update the displayed file name and type (labels and elision state)."""
        self._file_name = file_name
        self.texts = File.Text(file_name=file_name, file_type=file_type)
        self._file_type_label.setText(file_type.upper())
        self._pending_name_elide_retry = False
        self.refresh_display()


class OTPType(Enum):
    """
    OTP type.
    """

    IP = "IP"
    PORT = "Port"
    ASSOCIATION_CODE = "Association Code"


class OTPValidator(Enum):
    """
    OTP validator.
    """

    IP = QIntValidator()
    PORT = QIntValidator(0, 9)
    ASSOCIATION_CODE = QIntValidator(0, 9)


class OTPLineEdit(QLineEdit, Component):
    """
    QLineEdit subclass to handle backspace focus navigation and paste event for autofill.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on a single OTP cell."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the OTP cell."""

        pass

    def __init__(self, owner, index, *args, **kwargs):
        """Single OTP digit field wired to a parent ``OTPInput``.

        Args:
            owner: Parent ``OTPInput`` coordinating focus and paste.
            index: Zero-based cell index within the OTP sequence.
            *args: Forwarded to ``QLineEdit`` (typically parent).
            **kwargs: Forwarded to ``QLineEdit``.
        """
        super().__init__(*args, **kwargs)
        self.texts = OTPLineEdit.Text()
        self.ui = OTPLineEdit.UI()
        self._otp_parent = owner
        self._otp_index = index
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace:
            cursor_pos = self.cursorPosition()
            if cursor_pos == 0 and (not QLineEdit.text(self)) and self._otp_index > 0:
                # Move focus to previous field if not first field and field is empty
                prev_input = self._otp_parent._otp_inputs[self._otp_index - 1]
                prev_input.setFocus()
                prev_input.setCursorPosition(len(prev_input.text()))
                event.accept()
                return
        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Override paste event to autofill OTP fields."""
        text = source.text()
        if not text:
            return
        parent = self._otp_parent
        max_length = parent._max_length
        start_idx = self._otp_index
        idx = 0
        for i in range(start_idx, len(parent._otp_inputs)):
            current_len = max_length[i]
            chunk = text[idx : idx + current_len]
            parent._otp_inputs[i].setText(chunk)
            idx += len(chunk)
            if idx >= len(text):
                break
        # Optionally, move focus to next empty field (better UX)
        for i in range(start_idx, len(parent._otp_inputs)):
            if parent._otp_inputs[i].text() == "":
                parent._otp_inputs[i].setFocus()
                break
        else:
            parent._otp_inputs[-1].setFocus()


class OTPInput(QWidget, Component):
    """
    OTP input widget.
    """

    @dataclass(frozen=True)
    class Text:
        """Reserved for future user-visible strings on the OTP composite."""

        pass

    @dataclass
    class UI:
        """Reserved for future explicit child references on the OTP composite."""

        pass

    def __init__(
        self,
        parent: QWidget = None,
        otp_type: OTPType = OTPType.IP,
        otp_length: int = 6,
        max_length: list[int] = [1, 1, 1, 1, 1, 1],
        echo_mode: QLineEdit.EchoMode = QLineEdit.EchoMode.Normal,
    ):
        """Lay out a row of validated OTP cells.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            otp_type: Validation and grouping mode (IP, port, or association code).
            otp_length: Number of digit boxes.
            max_length: Per-cell max lengths; length must match ``otp_length``.
            echo_mode: Echo mode forwarded to each ``QLineEdit``.
        """
        assert (
            len(max_length) == otp_length
        ), "Max length list must be the same length as the OTP length"
        super().__init__(parent)
        self.texts = OTPInput.Text()
        self.ui = OTPInput.UI()

        self.setObjectName("otp-input")
        self._otp_type = otp_type
        self._otp_length = otp_length
        self._max_length = max_length
        self._echo_mode = echo_mode
        self._otp_inputs: list[QLineEdit] = []
        layout = QHBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.XS)

        for i in range(self._otp_length):
            otp_input = OTPLineEdit(self, i, self)
            otp_input.setObjectName(f"otp-input-{i}")
            otp_input.setFrame(True)
            otp_input.setFixedSize(
                Settings.DIMENSION.OTP_INPUT_SIZE, Settings.DIMENSION.OTP_INPUT_SIZE
            )
            otp_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
            otp_input.setCursor(Qt.CursorShape.IBeamCursor)
            otp_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            otp_input.setEchoMode(self._echo_mode)
            otp_input.setMaxLength(self._max_length[i])
            otp_input.setInputMethodHints(Qt.InputMethodHint.ImhDigitsOnly)
            if otp_type == OTPType.IP:
                otp_input.setValidator(OTPValidator.IP.value)
            elif otp_type == OTPType.PORT:
                otp_input.setValidator(OTPValidator.PORT.value)
            elif otp_type == OTPType.ASSOCIATION_CODE:
                otp_input.setValidator(OTPValidator.ASSOCIATION_CODE.value)
            otp_input.textChanged.connect(
                lambda text, idx=i: self._on_otp_text_changed(idx, text)
            )

            layout.addWidget(otp_input)
            self._otp_inputs.append(otp_input)

        self.setLayout(layout)

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        pass

    def _set_alignment(self) -> None:
        pass

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass

    def _on_otp_text_changed(self, index: int, text: str) -> None:
        if index < self._otp_length - 1 and len(text) == self._max_length[index]:
            self._otp_inputs[index + 1].setFocus()

    def is_valid(self) -> bool:
        for otp_input in self._otp_inputs:
            if not otp_input.hasAcceptableInput():
                return False
        return True

    def get_invalid_index(self) -> set[int]:
        invalid_indices_by_type: set[int] = set()
        invalid_indices_by_length: set[int] = set()
        for i, otp_input in enumerate(self._otp_inputs):
            if len(otp_input.text()) < self._max_length[i]:
                invalid_indices_by_length.add(i)
            if not otp_input.hasAcceptableInput():
                invalid_indices_by_type.add(i)
        return invalid_indices_by_type | invalid_indices_by_length

    def text(self) -> str:
        """Get the text of the OTP input. If the OTP type is IP, return the IP address. If the OTP type is PORT, return the port number. If the OTP type is ASSOCIATION_CODE, return the association code."""
        if self._otp_type == OTPType.IP:
            return ".".join([otp_input.text() for otp_input in self._otp_inputs])
        elif self._otp_type == OTPType.PORT:
            return "".join([otp_input.text() for otp_input in self._otp_inputs])
        elif self._otp_type == OTPType.ASSOCIATION_CODE:
            return "".join([otp_input.text() for otp_input in self._otp_inputs])
        else:
            return ""

    def clear(self) -> None:
        """Clear the OTP inputs."""
        for otp_input in self._otp_inputs:
            otp_input.clear()


class AuthentificationCard(QFrame, Component):
    """
    Card widget.
    """

    @dataclass(frozen=True)
    class Text:
        """Titles, descriptions, helper labels, and action copy for the card."""

        title: str | None = None
        description: str | None = None
        close_button_tooltip: Final[str] = "Close"
        helper_ip_otp_input: Final[str] = "IP address"
        helper_port_otp_input: Final[str] = "Port"
        helper_association_code_otp_input: Final[str] = "Association code"
        confirm_button: Final[str] = "Confirm"

    @dataclass
    class UI:
        """Composed widgets for credentials, OTP inputs, and confirm."""

        close_button: ToolButton
        icon: SVG
        icon_center_row: HorizontalLayoutWrapper
        icon_wrapper: HorizontalLayoutWrapper
        title: DemiBoldText
        description: HelperText
        helper_ip_otp_input: HelperText
        ip_otp_input: OTPInput
        ip_otp_input_wrapper: VerticalLayoutWrapper
        port_otp_input: OTPInput
        helper_port_otp_input: HelperText
        port_otp_input_wrapper: VerticalLayoutWrapper
        association_code_otp_input: OTPInput
        helper_association_code_otp_input: HelperText
        association_code_otp_input_wrapper: VerticalLayoutWrapper
        device_otp_wrapper: HorizontalLayoutWrapper
        confirm_button: Button

    def __init__(
        self,
        parent: QWidget = None,
        title: str = None,
        icon_path: str = None,
        description: str = None,
    ):
        """Build the authentification card with OTP rows and confirm action.

        Args:
            parent: Optional Qt parent widget for lifetime and hierarchy.
            title: Card heading text.
            icon_path: Optional hero icon asset above the title.
            description: Supporting text under the title.
        """
        super().__init__(parent)

        self.texts = AuthentificationCard.Text(title=title, description=description)
        self.ui: AuthentificationCard.UI
        self.setObjectName("card")
        self.setProperty("authentification-card", True)
        layout = QVBoxLayout()
        layout.setContentsMargins(*Settings.SPACING.MARGIN_SMALL)
        layout.setSpacing(Settings.SPACING.XS)

        close_button = ToolButton(
            self,
            icon=GenericIcons.X,
            tooltip=self.texts.close_button_tooltip,
        )

        if icon_path:
            icon = SVG(icon_path, self)
            icon.setFixedSize(get_svg_size(Settings.FONT.SIZE_TITLE))

        icon_center_row = HorizontalLayoutWrapper(
            self,
            margins=(0, Settings.SPACING.XS, 0, 0),
            widgets=[icon] if icon_path else [],
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        icon_wrapper = HorizontalLayoutWrapper(
            self, widgets=[icon_center_row, close_button]
        )
        icon_wrapper.get_layout().setStretch(0, 1)
        layout.addWidget(icon_wrapper, 1)

        if title:
            title_label = DemiBoldText(self, title)
            layout.addWidget(title_label)

        if description:
            description_label = HelperText(self, description)
            layout.addWidget(description_label)

        helper_ip_otp_input = HelperText(self, self.texts.helper_ip_otp_input)
        ip_otp_input = OTPInput(
            self,
            otp_type=OTPType.IP,
            otp_length=4,
            max_length=[3, 3, 1, 2],
            echo_mode=QLineEdit.EchoMode.Normal,
        )
        ip_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_ip_otp_input, ip_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        helper_port_otp_input = HelperText(self, self.texts.helper_port_otp_input)
        port_otp_input = OTPInput(
            self,
            otp_type=OTPType.PORT,
            otp_length=5,
            max_length=[1, 1, 1, 1, 1],
            echo_mode=QLineEdit.EchoMode.Normal,
        )
        port_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_port_otp_input, port_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        helper_association_code_otp_input = HelperText(
            self, self.texts.helper_association_code_otp_input
        )
        association_code_otp_input = OTPInput(
            self,
            otp_type=OTPType.ASSOCIATION_CODE,
            otp_length=6,
            max_length=[1, 1, 1, 1, 1, 1],
            echo_mode=QLineEdit.EchoMode.PasswordEchoOnEdit,
        )
        association_code_otp_input_wrapper = VerticalLayoutWrapper(
            self,
            widgets=[helper_association_code_otp_input, association_code_otp_input],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )

        device_otp_wrapper = HorizontalLayoutWrapper(
            self,
            widgets=[ip_otp_input_wrapper, port_otp_input_wrapper],
            spacing=Settings.SPACING.XS,
            stretch_at_beginning=True,
            stretch_at_end=True,
        )
        layout.addWidget(device_otp_wrapper)
        layout.addWidget(association_code_otp_input_wrapper)

        confirm_button = Button(self, self.texts.confirm_button)
        layout.addWidget(confirm_button, 1)

        self.setLayout(layout)

        self.ui = AuthentificationCard.UI(
            close_button=close_button,
            icon=icon,
            icon_center_row=icon_center_row,
            title=title_label,
            icon_wrapper=icon_wrapper,
            description=description_label,
            helper_ip_otp_input=helper_ip_otp_input,
            ip_otp_input=ip_otp_input,
            ip_otp_input_wrapper=ip_otp_input_wrapper,
            port_otp_input=port_otp_input,
            helper_port_otp_input=helper_port_otp_input,
            port_otp_input_wrapper=port_otp_input_wrapper,
            association_code_otp_input=association_code_otp_input,
            helper_association_code_otp_input=helper_association_code_otp_input,
            association_code_otp_input_wrapper=association_code_otp_input_wrapper,
            device_otp_wrapper=device_otp_wrapper,
            confirm_button=confirm_button,
        )

        # Timers for invalid OTP highlight: smooth pulse (sine-driven level 0–10),
        # same timing family as device-list highlight.
        self._invalid_highlight_pulse_timer = QTimer(self)
        self._invalid_highlight_pulse_timer.setSingleShot(False)
        self._invalid_highlight_pulse_timer.timeout.connect(
            self._on_invalid_highlight_pulse_tick
        )
        self._invalid_highlight_stop_timer = QTimer(self)
        self._invalid_highlight_stop_timer.setSingleShot(True)
        self._invalid_highlight_stop_timer.timeout.connect(
            self.stop_invalid_otp_highlight
        )
        self._invalid_highlight_elapsed = QElapsedTimer()
        self._invalid_targets: dict[OTPInput, set[int]] = {}

        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(Settings.DIMENSION.AUTENTHIFICATION_CARD_MIN_WIDTH)
        self.setMaximumWidth(Settings.DIMENSION.AUTENTHIFICATION_CARD_MAX_WIDTH)
        self.ui.close_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.ui.icon_center_row.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ui.title.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.description.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.ui.confirm_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.ip_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.port_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.association_code_otp_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.ui.device_otp_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def _set_alignment(self) -> None:
        # self.layout().setAlignment(self.ui.icon_wrapper, Qt.AlignmentFlag.AlignCenter)
        icon_header_layout = self.ui.icon_wrapper.get_layout()
        icon_header_layout.setAlignment(
            self.ui.icon_center_row, Qt.AlignmentFlag.AlignTop
        )
        icon_header_layout.setAlignment(
            self.ui.close_button,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        self.ui.icon_center_row.get_layout().setAlignment(
            self.ui.icon,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )
        self.layout().setAlignment(self.ui.title, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(self.ui.description, Qt.AlignmentFlag.AlignCenter)
        self.layout().setAlignment(
            self.ui.ip_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.ip_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_ip_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.ip_otp_input_wrapper.get_layout().setAlignment(
            self.ui.ip_otp_input, Qt.AlignmentFlag.AlignLeft
        )
        self.layout().setAlignment(
            self.ui.port_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.port_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_port_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.port_otp_input_wrapper.get_layout().setAlignment(
            self.ui.port_otp_input, Qt.AlignmentFlag.AlignLeft
        )
        self.layout().setAlignment(
            self.ui.association_code_otp_input_wrapper, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.association_code_otp_input_wrapper.get_layout().setAlignment(
            self.ui.helper_association_code_otp_input, Qt.AlignmentFlag.AlignCenter
        )
        self.ui.association_code_otp_input_wrapper.get_layout().setAlignment(
            self.ui.association_code_otp_input, Qt.AlignmentFlag.AlignLeft
        )

    def _connect_signals(self) -> None:
        self.ui.confirm_button.clicked.connect(self._on_confirm_button_clicked)
        self.ui.close_button.clicked.connect(self._on_close_button_clicked)

    def apply_theme_icons(self, theme: Theme) -> None:
        self.ui.close_button.apply_theme_icons(theme)
        self.ui.icon.set_path(icon_qt_path_for_theme(theme, GenericIcons.DEVICE))

    def _on_close_button_clicked(self) -> None:
        """Handle the close button clicked event."""
        view_signals.AuthentificationCancelled.emit()

    def _is_ip_otp_input_valid(self) -> bool:
        return self.ui.ip_otp_input.is_valid()

    def _is_port_otp_input_valid(self) -> bool:
        return self.ui.port_otp_input.is_valid()

    def _is_association_code_otp_input_valid(self) -> bool:
        return self.ui.association_code_otp_input.is_valid()

    def _on_confirm_button_clicked(self) -> None:

        raise_signal: bool = True

        if self._is_ip_otp_input_valid():
            logger.info("IP adress for authentification is valid.")
        else:
            logger.info("IP adress for authentification is invalid.")
            raise_signal = False

        if self._is_port_otp_input_valid():
            logger.info("Port for authentification is valid.")
        else:
            logger.info("Port for authentification is invalid.")
            raise_signal = False

        if self._is_association_code_otp_input_valid():
            logger.info("Association code for authentification is valid.")
        else:
            logger.info("Association code for authentification is invalid.")
            raise_signal = False

        if raise_signal:
            view_signals.AuthentificationConfirmed.emit(
                self.ui.ip_otp_input.text(),
                self.ui.port_otp_input.text(),
                self.ui.association_code_otp_input.text(),
            )
        else:
            self.start_invalid_otp_highlight()

    def _otp_sections(self) -> list[tuple[HelperText, OTPInput]]:
        return [
            (self.ui.helper_ip_otp_input, self.ui.ip_otp_input),
            (self.ui.helper_port_otp_input, self.ui.port_otp_input),
            (
                self.ui.helper_association_code_otp_input,
                self.ui.association_code_otp_input,
            ),
        ]

    def _set_invalid_otp_highlight_level(self, level: int) -> None:
        for helper_label, otp_group in self._otp_sections():
            invalid_indices = self._invalid_targets.get(otp_group, set())
            helper_level = level if invalid_indices else 0
            apply_highlight_level(
                helper_label, "otp-helper-invalid-highlight-level", helper_level
            )
            for i, otp_line_edit in enumerate(otp_group._otp_inputs):
                line_level = level if i in invalid_indices else 0
                apply_highlight_level(
                    otp_line_edit, "otp-invalid-highlight-level", line_level
                )

    def _on_invalid_highlight_pulse_tick(self) -> None:
        cycle_ms = Settings.ANIMATION.ATTENTION_HIGHLIGHT_PULSE_CYCLE_MS
        elapsed = self._invalid_highlight_elapsed.elapsed()
        level = compute_sine_pulse_level(elapsed, cycle_ms)
        self._set_invalid_otp_highlight_level(level)

    def start_invalid_otp_highlight(self) -> None:
        """Start smooth error pulse on invalid OTP inputs and their helper labels."""
        self.stop_invalid_otp_highlight()
        self._invalid_targets = {}
        for _, otp_group in self._otp_sections():
            invalid_indices = set(otp_group.get_invalid_index())
            if invalid_indices:
                self._invalid_targets[otp_group] = invalid_indices
        if not self._invalid_targets:
            return
        self._invalid_highlight_elapsed.start()
        self._invalid_highlight_pulse_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_UPDATE_MS
        )
        self._invalid_highlight_stop_timer.start(
            Settings.ANIMATION.ATTENTION_HIGHLIGHT_DURATION
        )

    def stop_invalid_otp_highlight(self) -> None:
        """Stop OTP invalid highlight animation and restore default label/input styles."""
        self._invalid_highlight_pulse_timer.stop()
        self._invalid_highlight_stop_timer.stop()
        self._set_invalid_otp_highlight_level(0)

    def clear(self) -> None:
        """Clear the OTP inputs."""
        for _, otp_input in self._otp_sections():
            otp_input.clear()
        self.stop_invalid_otp_highlight()

    def showEvent(self, event: QShowEvent) -> None:
        """Clear the OTP inputs when the card is shown."""
        self.clear()
        logger.info("Authentification card cleared.")
        super().showEvent(event)
