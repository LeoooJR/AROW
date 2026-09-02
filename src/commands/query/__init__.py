"""Read-only data query commands."""

import typer

from commands.query.milestone import milestone
from commands.query.railway import railway

app = typer.Typer(no_args_is_help=True)
app.command(name="milestone", context_settings={"ignore_unknown_options": True})(
    milestone
)
app.command(name="railway", context_settings={"ignore_unknown_options": True})(railway)

__all__ = ["app"]
