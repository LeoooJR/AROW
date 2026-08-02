"""Run commands for the application."""

from typing import Annotated

import typer

from commands.run.gui import gui
from commands.run.options import RunOptions

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
) -> None:
    """Run AROW with the selected user interface."""
    context.obj = RunOptions(
        mock_adb=mock_adb,
        serialize_logs=json_logs,
    )

    if context.invoked_subcommand is None:
        raise typer.Exit(1)


app.command(name="gui")(gui)

__all__ = ["RunOptions", "app"]
