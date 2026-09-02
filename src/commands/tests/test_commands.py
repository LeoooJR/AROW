"""Tests for the root application command tree."""

from typer.testing import CliRunner

from commands import app

runner = CliRunner()


def test_root_help_lists_command_groups() -> None:
    """The root application exposes its command groups."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--json-logs" not in result.stdout
    assert "--log-dir" not in result.stdout
    assert "query" in result.stdout
    assert "run" in result.stdout


def test_query_help_lists_data_commands() -> None:
    """The query group exposes its railway data lookup commands."""
    result = runner.invoke(app, ["query", "--help"])

    assert result.exit_code == 0
    assert "milestone" in result.stdout
    assert "railway" in result.stdout


def test_run_help_lists_gui_command() -> None:
    """The run group exposes its shared option and GUI subcommand."""
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "--json-logs" in result.stdout
    assert "--log-dir" in result.stdout
    assert "--mock-adb" in result.stdout
    assert "gui" in result.stdout


def test_gui_help_does_not_duplicate_run_options() -> None:
    """Shared run options are not repeated on individual interfaces."""
    result = runner.invoke(app, ["run", "gui", "--help"])

    assert result.exit_code == 0
    assert "--json-logs" not in result.stdout
    assert "--log-dir" not in result.stdout
    assert "--mock-adb" not in result.stdout


def test_run_rejects_mock_adb_after_subcommand() -> None:
    """Run-group options must precede the selected interface."""
    result = runner.invoke(app, ["run", "gui", "--mock-adb"])

    assert result.exit_code == 2
    assert "No such option" in result.stderr


def test_run_without_subcommand_exits_for_unimplemented_tui() -> None:
    """Bare ``run`` reserves the default path for the future TUI."""
    for arguments in (["run"], ["run", "--mock-adb"]):
        result = runner.invoke(app, arguments)

        assert result.exit_code == 1
        assert result.stdout == ""
