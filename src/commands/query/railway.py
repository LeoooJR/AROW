"""Command for querying a railway from the bundled referentials."""

from typing import Annotated

import typer
from rich.text import Text

from commands.query.presentation import MetadataSections, QueryMetadataCard
from commands.query.validators import validate_railway_code, validate_section
from commands.style import create_console
from core.geo.exceptions import RailwayValidationError
from core.geo.railway import Railway


def railway(
    railway_code: Annotated[
        str,
        typer.Argument(
            help="Six-digit railway code.",
            callback=validate_railway_code,
            metavar="RAILWAY_CODE",
        ),
    ],
    section: Annotated[
        int,
        typer.Argument(
            help="Positive railway section number.",
            callback=validate_section,
            metavar="SECTION",
        ),
    ],
) -> None:
    """Find and display one railway."""
    try:
        resolved_railway = Railway.validate(code=railway_code, troncon=section)
    except RailwayValidationError as error:
        message = Text.assemble(
            ("Railway lookup failed: ", "arow.error"),
            str(error),
        )
        create_console(stderr=True).print(message)
        raise typer.Exit(1) from error

    sections: MetadataSections = (
        (
            "Railway",
            (
                ("Gaïa ID", resolved_railway.id),
                ("Code", resolved_railway.code),
                ("Section", str(resolved_railway.troncon)),
                ("Label", resolved_railway.label),
                ("Type", resolved_railway.type),
            ),
        ),
    )
    primary_key = f"{resolved_railway.code}-{resolved_railway.troncon}"
    subtitle = f"line {resolved_railway.code} · section {resolved_railway.troncon}"
    console = create_console()
    console.print(
        QueryMetadataCard(
            title="Railway target",
            subtitle=subtitle,
            sections=sections,
            primary_key=primary_key,
            terminal_width=console.width,
        )
    )


__all__ = ["railway"]
