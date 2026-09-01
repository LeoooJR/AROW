"""Application command groups."""

import typer

from commands.query import app as query_app
from commands.run import app as run_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(query_app, name="query")
app.add_typer(run_app, name="run")

__all__ = ["app"]
