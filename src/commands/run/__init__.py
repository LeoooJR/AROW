"""Run commands for the application."""

import typer

from commands.run.gui import gui

app = typer.Typer()


@app.callback(invoke_without_command=True)
def run(context: typer.Context) -> None:
    """Run AROW with the selected user interface."""
    if context.invoked_subcommand is None:
        raise typer.Exit(1)


app.command(name="gui")(gui)

__all__ = ["app"]
