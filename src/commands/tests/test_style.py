"""Tests for the shared AROW CLI presentation convention."""

import pytest
from typer import rich_utils

from commands import app
from commands.query import app as query_app
from commands.run import app as run_app
from commands.style import AROW_TYPER_STYLES, configure_typer_styles


def test_typer_rich_output_uses_arow_semantic_styles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typer help and errors reuse the application palette."""
    monkeypatch.setattr(rich_utils, "STYLE_OPTION", "bold cyan")

    configure_typer_styles()

    for attribute, expected_style in AROW_TYPER_STYLES.items():
        assert getattr(rich_utils, attribute) == expected_style


def test_all_command_groups_use_shared_rich_defaults() -> None:
    """Every command group enables the same safe Rich rendering settings."""
    for command_app in (app, query_app, run_app):
        assert command_app.rich_markup_mode == "rich"
        assert command_app.pretty_exceptions_show_locals is False
