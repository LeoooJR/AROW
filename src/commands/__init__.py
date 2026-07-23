"""Application command groups."""

import typer

from commands.run import app as run_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(run_app, name="run")

__all__ = ["app"]
