"""Tests for the root application command tree."""

from typer.testing import CliRunner

from commands import app

runner = CliRunner()


def test_root_help_lists_run_command() -> None:
    """The root application exposes commands grouped under ``run``."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.stdout


def test_run_help_lists_gui_command() -> None:
    """The run group exposes the GUI implementation as a subcommand."""
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "gui" in result.stdout


def test_run_without_subcommand_exits_for_unimplemented_tui() -> None:
    """Bare ``run`` reserves the default path for the future TUI."""
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert result.stdout == ""
