"""Tests for the root application command tree."""

import pytest
from typer.testing import CliRunner

from commands import app

runner = CliRunner()

PUBLIC_RUN_ENVIRONMENT_VARIABLES = (
    "AROW_USE_MOCK_ADB",
    "AROW_MOCK_ADB_SEED",
    "AROW_LOG_FALLBACK_DIR",
)
PRIVATE_ENVIRONMENT_VARIABLES = (
    "AROW_LOG_FILE",
    "AROW_LOG_SERIALIZE",
    "AROW_GUI_TEST_SCREEN_SIZE",
    "AROW_GUI_SCREENSHOT_DIR",
)


def _normalized_help(arguments: list[str]) -> str:
    result = runner.invoke(app, arguments, terminal_width=120)
    assert result.exit_code == 0
    return " ".join(result.stdout.replace("│", " ").split())


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


@pytest.mark.parametrize("arguments", [["run", "--help"], ["run", "gui", "--help"]])
def test_run_help_documents_public_environment_variables(
    arguments: list[str],
) -> None:
    """Runtime help explains every supported user environment variable."""
    output = _normalized_help(arguments)

    for variable in PUBLIC_RUN_ENVIRONMENT_VARIABLES:
        assert variable in output
    for expected_detail in (
        "1, true, or yes",
        "without --mock-adb",
        "repeatable mock-device data",
        "invalid values are ignored",
        "default low-level log location is unwritable",
        "ignored when --log-dir is supplied",
    ):
        assert expected_detail in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["query", "--help"],
        ["query", "milestone", "--help"],
        ["query", "railway", "--help"],
    ],
)
def test_unrelated_help_omits_runtime_environment_variables(
    arguments: list[str],
) -> None:
    """Query and root help stay focused on their own available behavior."""
    output = _normalized_help(arguments)

    for variable in PUBLIC_RUN_ENVIRONMENT_VARIABLES:
        assert variable not in output


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["run", "--help"],
        ["run", "gui", "--help"],
        ["query", "--help"],
        ["query", "milestone", "--help"],
        ["query", "railway", "--help"],
    ],
)
def test_cli_help_never_exposes_private_environment_variables(
    arguments: list[str],
) -> None:
    """Internally managed and test-only environment variables remain private."""
    output = _normalized_help(arguments)

    for variable in PRIVATE_ENVIRONMENT_VARIABLES:
        assert variable not in output


def test_gui_help_does_not_duplicate_run_option_panels() -> None:
    """Shared run option controls are not repeated on individual interfaces."""
    result = runner.invoke(app, ["run", "gui", "--help"])

    assert result.exit_code == 0
    assert "--json-logs" not in result.stdout
    assert "ADB Options" not in result.stdout
    assert "Logging Options" not in result.stdout
    assert result.stdout.count("--log-dir") == 1
    assert result.stdout.count("--mock-adb") == 1


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
