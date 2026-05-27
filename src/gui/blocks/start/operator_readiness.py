"""Welcome operator-readiness block."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from gui.blocks.base import Block
from gui.colors import Theme
from gui.settings import Settings
from gui.wrapper import HorizontalLayoutWrapper, VerticalLayoutWrapper


class ReadinessRow(HorizontalLayoutWrapper):
    """Compact operator-readiness status row."""

    @dataclass(frozen=True)
    class Text:
        label: str
        detail: str
        status: str

    @dataclass
    class UI:
        label: QLabel
        detail: QLabel
        status: QLabel
        text_wrapper: VerticalLayoutWrapper

    def __init__(
        self,
        parent: QWidget | None,
        *,
        label: str,
        detail: str,
        status: str,
        status_kind: str = "muted",
    ) -> None:
        self.texts = ReadinessRow.Text(label=label, detail=detail, status=status)

        label_widget = QLabel(label, parent)
        label_widget.setObjectName("readiness-row-label")
        label_widget.setProperty("readiness-row-label", True)

        detail_widget = QLabel(detail, parent)
        detail_widget.setObjectName("readiness-row-detail")
        detail_widget.setProperty("readiness-row-detail", True)

        text_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=[label_widget, detail_widget],
            spacing=2,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        text_wrapper.setObjectName("readiness-row-text")

        status_widget = QLabel(status, parent)
        status_widget.setObjectName("readiness-status-chip")
        status_widget.setProperty("readiness-status-chip", status_kind)

        super().__init__(
            parent,
            widgets=[text_wrapper, status_widget],
            spacing=Settings.SPACING.SM,
            margins=Settings.SPACING.MARGIN_SMALL,
        )
        self.setObjectName("readiness-row")
        self.setProperty("readiness-row", True)
        self.ui = ReadinessRow.UI(
            label=label_widget,
            detail=detail_widget,
            status=status_widget,
            text_wrapper=text_wrapper,
        )
        self.get_layout().setStretchFactor(text_wrapper, 1)
        self.get_layout().setAlignment(status_widget, Qt.AlignmentFlag.AlignVCenter)


class OperatorReadinessBlock(VerticalLayoutWrapper, Block):
    """Welcome card summarizing operator workflow readiness."""

    @dataclass(frozen=True)
    class Text:
        title: Final[str] = "Operator readiness"
        rows: tuple[tuple[str, str, str, str], ...] = (
            ("Host ready", "ADB bridge standing by", "READY", "ready"),
            ("Device link", "Awaiting trusted Android target", "OPEN", "muted"),
            ("Location set", "Railway milestone not assigned", "PENDING", "muted"),
            (
                "Simulation armed",
                "Start locked until target is selected",
                "LOCKED",
                "muted",
            ),
        )

    @dataclass
    class UI:
        title: QLabel
        rows_wrapper: VerticalLayoutWrapper
        rows: list[ReadinessRow]

    def __init__(self, parent: QWidget | None = None) -> None:
        block_texts = OperatorReadinessBlock.Text()

        title = QLabel(block_texts.title, parent)
        title.setProperty("welcome-section-title", True)

        row_widgets = [
            ReadinessRow(
                parent,
                label=label,
                detail=detail,
                status=status,
                status_kind=status_kind,
            )
            for label, detail, status, status_kind in block_texts.rows
        ]
        rows_wrapper = VerticalLayoutWrapper(
            parent,
            widgets=row_widgets,
            spacing=Settings.SPACING.XS,
            margins=Settings.SPACING.MARGIN_NONE,
        )
        rows_wrapper.setObjectName("readiness-rows-wrapper")

        super().__init__(
            parent,
            widgets=[title, rows_wrapper],
            spacing=Settings.PANEL.SECTION_SPACING,
            margins=(
                Settings.WELCOME.CARD_PADDING_LEFT,
                Settings.WELCOME.CARD_PADDING_TOP,
                Settings.WELCOME.CARD_PADDING_RIGHT,
                Settings.WELCOME.CARD_PADDING_BOTTOM,
            ),
        )
        self.setObjectName("welcome-operator-readiness-card")
        self.setProperty("welcome-card", True)
        self.texts = block_texts
        self.ui = OperatorReadinessBlock.UI(
            title=title,
            rows_wrapper=rows_wrapper,
            rows=row_widgets,
        )
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.ui.rows_wrapper.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

    def _set_alignment(self) -> None:
        self.ui.title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

    def _connect_signals(self) -> None:
        pass

    def apply_theme_icons(self, theme: Theme) -> None:
        pass


__all__ = ["OperatorReadinessBlock", "ReadinessRow"]
