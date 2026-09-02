"""Command for querying a milestone from the bundled railway referentials."""

from io import StringIO
from typing import Annotated, Final

import segno
import typer
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from commands.style import create_console
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.geo.milestone import Milestone
from core.geo.railway import Railway

_QR_SIDE_BY_SIDE_MIN_WIDTH: Final[int] = 96
_STANDARD_QR_TERMINAL_WIDTH: Final[int] = 29


def _railway_code(value: str) -> str:
    """Require the official six-digit numeric railway code format."""
    if len(value) != 6 or not value.isdigit():
        raise typer.BadParameter("must contain exactly six digits")
    return value


def _milestone_qr(milestone: Milestone) -> Text:
    """Render the canonical milestone ID as a compact standard terminal QR code."""
    qr_code = segno.make(milestone.id, micro=False)
    output = StringIO()
    qr_code.terminal(out=output, compact=True)
    rows = output.getvalue().rstrip("\n").splitlines()
    if rows and rows[-1] == "▀" * len(rows[-1]):
        # Segno pairs the odd final quiet-zone row with a transparent lower half.
        # Complete that lower half in white instead of exposing the black canvas.
        rows[-1] = "█" * len(rows[-1])
    return Text(
        "\n".join(rows),
        style="#ffffff on #000000",
        no_wrap=True,
        overflow="crop",
    )


def _metadata_card(milestone: Milestone, *, terminal_width: int) -> Panel:
    """Build a terminal card for a validated milestone and its railway."""
    line = milestone.line
    metadata = Table.grid(padding=(0, 2), expand=True)
    metadata.add_column(style="arow.muted", no_wrap=True)
    metadata.add_column(style="bold")

    sections: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
        (
            "Milestone",
            (
                ("Label", milestone.label),
                ("Kilometer", str(milestone.km)),
                ("Type", milestone.type),
                ("Latitude", f"{milestone.geometry.y:.6f}"),
                ("Longitude", f"{milestone.geometry.x:.6f}"),
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
    for section_index, (section_title, rows) in enumerate(sections):
        if section_index:
            metadata.add_row()
        metadata.add_row(Text(section_title, style="arow.primary"), "")
        for label, value in rows:
            metadata.add_row(label, value)

    qr_code = _milestone_qr(milestone)
    if terminal_width >= _QR_SIDE_BY_SIDE_MIN_WIDTH:
        content = Table.grid(expand=True)
        content.add_column(ratio=1)
        content.add_column(width=3)
        content.add_column(width=_STANDARD_QR_TERMINAL_WIDTH, no_wrap=True)
        content.add_row(metadata, "", qr_code)
    else:
        content = Group(metadata, Text(""), qr_code)

    title = Text.assemble(
        ("Milestone target", "bold"),
        ("  ● Ready", "arow.success"),
    )
    subtitle = Text(
        f"PK {milestone.label} · line {line.code} · section {line.troncon}",
        style="arow.muted",
    )
    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        title_align="left",
        subtitle_align="left",
        border_style="arow.border",
        box=box.ROUNDED,
        padding=(1, 2),
        expand=False,
    )


def milestone(
    railway_code: Annotated[
        str,
        typer.Argument(
            help="Six-digit railway code.",
            callback=_railway_code,
            metavar="RAILWAY_CODE",
        ),
    ],
    section: Annotated[
        int,
        typer.Argument(
            help="Positive railway section number.",
            min=1,
            metavar="SECTION",
        ),
    ],
    milestone_code: Annotated[
        int,
        typer.Argument(
            help="Positive milestone kilometer code.",
            min=1,
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

    console = create_console()
    console.print(_metadata_card(resolved_milestone, terminal_width=console.width))


__all__ = ["milestone"]
