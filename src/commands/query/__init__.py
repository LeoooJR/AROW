"""Read-only data query commands."""

import typer

from commands.query.milestone import milestone

app = typer.Typer(no_args_is_help=True)
app.command(name="milestone")(milestone)

__all__ = ["app"]
