"""Tests for the abstract block lifecycle contract."""

from __future__ import annotations

from gui.blocks.base import Block


def test_block_declares_required_lifecycle_methods() -> None:
    """The block base class marks all lifecycle hooks as abstract contract methods."""
    for method_name in (
        "_set_size_policy",
        "_set_alignment",
        "_connect_signals",
        "apply_theme_icons",
    ):
        method = getattr(Block, method_name)
        assert getattr(method, "__isabstractmethod__", False) is True


def test_block_finalize_ui_hooks_runs_lifecycle_methods() -> None:
    """The shared finalize hook calls size, alignment, then signal hooks."""

    class ConcreteBlock(Block):
        def __init__(self) -> None:
            self.calls: list[str] = []

        def _set_size_policy(self) -> None:
            self.calls.append("size")

        def _set_alignment(self) -> None:
            self.calls.append("alignment")

        def _connect_signals(self) -> None:
            self.calls.append("signals")

        def apply_theme_icons(self, theme) -> None:  # type: ignore[no-untyped-def]
            self.calls.append(f"theme:{theme}")

    block = ConcreteBlock()

    block._finalize_ui_hooks()

    assert block.calls == ["size", "alignment", "signals"]
