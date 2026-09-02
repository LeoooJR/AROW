"""Run commands for the application."""

from pathlib import Path
from typing import Annotated

import typer

from commands.run.gui import gui
from commands.run.options import RunOptions
from commands.style import configure_typer_styles

configure_typer_styles()
app = typer.Typer()


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


app.command(name="gui")(gui)

__all__ = ["RunOptions", "app"]
