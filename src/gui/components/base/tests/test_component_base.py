"""Tests for the component base lifecycle."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from gui.components.base import Component

pytestmark = pytest.mark.usefixtures("qapp")


class DummyComponent(QWidget, Component):
    """Concrete component used to verify the base hook sequence."""

    def __init__(self):
        super().__init__()
        self.calls: list[str] = []
        self._finalize_ui_hooks()

    def _set_size_policy(self) -> None:
        self.calls.append("size")

    def _set_alignment(self) -> None:
        self.calls.append("alignment")

    def _connect_signals(self) -> None:
        self.calls.append("signals")

    def apply_theme_icons(self, theme) -> None:
        self.calls.append(f"theme:{theme}")


class ExplodingComponent(DummyComponent):
    """Component whose first hook fails."""

    def _set_size_policy(self) -> None:
        raise RuntimeError("size failed")


def test_component_finalize_runs_hooks_in_order(qtbot) -> None:
    component = DummyComponent()
    qtbot.addWidget(component)

    assert component.calls == ["size", "alignment", "signals"]


def test_component_finalize_propagates_hook_failures() -> None:
    with pytest.raises(RuntimeError, match="size failed"):
        ExplodingComponent()
