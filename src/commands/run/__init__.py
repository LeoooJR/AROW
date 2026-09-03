"""Run commands for the application."""

from pathlib import Path
from typing import Annotated, Final

import typer

from commands.run.gui import gui
from commands.run.options import RunOptions
from commands.style import configure_typer_styles

_ENVIRONMENT_HELP: Final[str] = (
    "[option]Environment variables[/option]\n\n"
    "[metavar]AROW_USE_MOCK_ADB[/metavar] —\n"
    "Set to 1, true, or yes to enable mock ADB without --mock-adb.\n\n"
    "[metavar]AROW_MOCK_ADB_SEED[/metavar] —\n"
    "Optional integer for repeatable mock-device data. It only applies in mock "
    "mode; invalid values are ignored.\n\n"
    "[metavar]AROW_LOG_FALLBACK_DIR[/metavar] —\n"
    "Directory used when the default low-level log location is unwritable. It is "
    "ignored when --log-dir is supplied."
)

configure_typer_styles()
app = typer.Typer(epilog=_ENVIRONMENT_HELP)


@app.callback(invoke_without_command=True)
def run(
    context: typer.Context,
    mock_adb: Annotated[
        bool,
        typer.Option(
            help="Use faker-backed mock ADB (no real adb daemon or binary).",
            rich_help_panel="ADB Options",
        ),
    ] = False,
    json_logs: Annotated[
        bool,
        typer.Option(
            "--json-logs",
            help="Write machine-readable JSON Lines logs for runtime analysis.",
            rich_help_panel="Logging Options",
        ),
    ] = False,
    log_dir: Annotated[
        Path | None,
        typer.Option(
            "--log-dir",
            help="Write application and worker logs to this directory.",
            file_okay=False,
            dir_okay=True,
            rich_help_panel="Logging Options",
        ),
    ] = None,
) -> None:
    """Run AROW with the selected user interface."""
    context.obj = RunOptions(
        mock_adb=mock_adb,
        serialize_logs=json_logs,
        log_dir=log_dir.expanduser().resolve(strict=False) if log_dir else None,
    )

    if context.invoked_subcommand is None:
        raise typer.Exit(1)


app.command(name="gui", epilog=_ENVIRONMENT_HELP)(gui)

__all__ = ["RunOptions", "app"]
