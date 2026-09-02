"""Command for querying a milestone from the bundled railway referentials."""

from typing import Annotated

import typer
from rich.text import Text

from commands.query.presentation import MetadataSections, QueryMetadataCard
from commands.query.validators import (
    validate_milestone_code,
    validate_railway_code,
    validate_section,
)
from commands.style import create_console
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.geo.milestone import Milestone
from core.geo.railway import Railway


def milestone(
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
    milestone_code: Annotated[
        int,
        typer.Argument(
            help="Positive milestone kilometer code.",
            callback=validate_milestone_code,
            metavar="MILESTONE_CODE",
        ),
    ],
) -> None:
    """Find and display one railway milestone."""
    try:
        line = Railway.validate(code=railway_code, troncon=section)
        resolved_milestone = Milestone.validate(km=milestone_code, line=line)
    except (RailwayValidationError, MilestoneValidationError) as error:
        message = Text.assemble(
            ("Milestone lookup failed: ", "arow.error"),
            str(error),
        )
        create_console(stderr=True).print(message)
        raise typer.Exit(1) from error

    line = resolved_milestone.line
    sections: MetadataSections = (
        (
            "Milestone",
            (
                ("Label", resolved_milestone.label),
                ("Kilometer", str(resolved_milestone.km)),
                ("Type", resolved_milestone.type),
                ("Latitude", f"{resolved_milestone.geometry.y:.6f}"),
                ("Longitude", f"{resolved_milestone.geometry.x:.6f}"),
            ),
        ),
        (
            "Railway",
            (
                ("Gaïa ID", line.id),
                ("Code", line.code),
                ("Section", str(line.troncon)),
                ("Label", line.label),
                ("Type", line.type),
            ),
        ),
    )
    console = create_console()
    console.print(
        QueryMetadataCard(
            title="Milestone target",
            subtitle=(
                f"PK {resolved_milestone.label} · line {line.code} · "
                f"section {line.troncon}"
            ),
            sections=sections,
            primary_key=resolved_milestone.id,
            terminal_width=console.width,
        )
    )


__all__ = ["milestone"]
