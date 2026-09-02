"""Tests for the milestone query command."""

from io import StringIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import pytest
from rich.console import Console
from rich.text import Text
from shapely.geometry import Point
from typer.testing import CliRunner

from commands import app
from commands.query.milestone import _metadata_card, _milestone_qr
from commands.style import AROW_THEME
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.geo.milestone import Milestone

runner = CliRunner()


def _railway() -> SimpleNamespace:
    return SimpleNamespace(
        id="47186fe6-6665-11e3-afff-01f464e0362d",
        code="001000",
        troncon=1,
        label="Ligne de Paris-Est à Mulhouse-Ville",
        type="Ligne proprement dite",
    )


def _milestone(line: SimpleNamespace) -> Milestone:
    return cast(
        Milestone,
        SimpleNamespace(
            id="001000-1-1",
            label="001+000",
            km=1,
            type="Kilometer",
            geometry=Point(2.363530409238113, 48.88533318609319),
            line=line,
        ),
    )


def _render_card(card, *, width: int) -> str:
    output = StringIO()
    Console(
        file=output,
        width=width,
        color_system=None,
        theme=AROW_THEME,
    ).print(card)
    return output.getvalue()


def test_milestone_qr_encodes_canonical_primary_key() -> None:
    """The QR payload is the standard milestone ID rendered in compact form."""
    milestone = _milestone(_railway())
    qr_code = Mock(name="qr_code")

    def write_terminal(*, out: StringIO, compact: bool) -> None:
        assert compact is True
        out.write("██\n▀▀\n")

    qr_code.terminal.side_effect = write_terminal
    with patch("commands.query.milestone.segno.make", return_value=qr_code) as make:
        rendered = _milestone_qr(milestone)

    make.assert_called_once_with("001000-1-1", micro=False)
    qr_code.terminal.assert_called_once()
    assert qr_code.terminal.call_args.kwargs["compact"] is True
    assert rendered.plain == "██\n██"
    assert rendered.no_wrap is True
    assert str(rendered.style) == "#ffffff on #000000"


@pytest.mark.parametrize(
    ("terminal_width", "side_by_side"),
    [(95, False), (96, True)],
)
def test_milestone_card_uses_responsive_qr_layout(
    terminal_width: int,
    side_by_side: bool,
) -> None:
    """The QR stacks below metadata until the wide-card breakpoint."""
    milestone = _milestone(_railway())

    with patch(
        "commands.query.milestone._milestone_qr",
        return_value=Text("QR-CODE", no_wrap=True),
    ):
        output = _render_card(
            _metadata_card(milestone, terminal_width=terminal_width),
            width=terminal_width,
        )

    assert "Milestone key" not in output
    assert "QR-CODE" in output
    metadata_shares_qr_row = any(
        "Milestone" in line and "QR-CODE" in line for line in output.splitlines()
    )
    assert metadata_shares_qr_row is side_by_side
    assert max(len(line) for line in output.splitlines()) <= terminal_width


def test_wide_qr_does_not_style_table_spacing() -> None:
    """The QR background ends with the symbol instead of covering right padding."""
    milestone = _milestone(_railway())
    qr_row = "█" * 29
    qr_code = Text(qr_row, style="#ffffff on #000000", no_wrap=True)
    console = Console(width=120, theme=AROW_THEME)

    with patch(
        "commands.query.milestone._milestone_qr",
        return_value=qr_code,
    ):
        card = _metadata_card(milestone, terminal_width=120)
        segments = list(console.render(card, console.options))

    background_segments = [
        segment.text
        for segment in segments
        if segment.style is not None and segment.style.bgcolor is not None
    ]
    assert background_segments == [qr_row]


def test_milestone_query_renders_complete_metadata_card() -> None:
    """A resolved milestone is rendered with metadata and its QR code."""
    railway = _railway()
    milestone = _milestone(railway)

    with (
        patch(
            "commands.query.milestone.Railway.validate", return_value=railway
        ) as validate_railway,
        patch(
            "commands.query.milestone.Milestone.validate", return_value=milestone
        ) as validate_milestone,
    ):
        result = runner.invoke(app, ["query", "milestone", "001000", "1", "1"])

    assert result.exit_code == 0
    validate_railway.assert_called_once_with(code="001000", troncon=1)
    validate_milestone.assert_called_once_with(km=1, line=railway)
    for expected in (
        "Milestone target",
        "Ready",
        "Milestone",
        "Railway",
        "█",
        "001000-1-1",
        "001+000",
        "Kilometer",
        "48.885333",
        "2.363530",
        "47186fe6-6665-11e3-afff-01f464e0362d",
        "001000",
        "Ligne de Paris-Est à Mulhouse-Ville",
        "Ligne proprement dite",
    ):
        assert expected in result.stdout
    assert "Milestone key" not in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ["query", "milestone", "1000", "1", "1"],
        ["query", "milestone", "ABCDEF", "1", "1"],
        ["query", "milestone", "001000", "0", "1"],
        ["query", "milestone", "001000", "1", "0"],
        ["query", "milestone", "001000", "-1", "1"],
        ["query", "milestone", "001000", "1", "-1"],
    ],
)
def test_milestone_query_rejects_invalid_arguments(arguments: list[str]) -> None:
    """CLI inputs must use a six-digit line code and positive integer indexes."""
    result = runner.invoke(app, arguments)

    assert result.exit_code == 2


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (
            RailwayValidationError("Unknown railway code_ligne: '999999'"),
            "Unknown railway code_ligne: '999999'",
        ),
        (
            MilestoneValidationError("Unknown milestone: '001000-1' 999"),
            "Unknown milestone: '001000-1' 999",
        ),
    ],
)
def test_milestone_query_reports_lookup_failure(
    error: Exception,
    expected_message: str,
) -> None:
    """Expected lookup failures are concise, non-zero, and traceback-free."""
    railway = _railway()
    railway_result = railway if isinstance(error, MilestoneValidationError) else error

    with (
        patch("commands.query.milestone.segno.make") as make_qr,
        patch(
            "commands.query.milestone.Railway.validate",
            side_effect=(
                railway_result if isinstance(railway_result, Exception) else None
            ),
            return_value=(
                None if isinstance(railway_result, Exception) else railway_result
            ),
        ),
        patch(
            "commands.query.milestone.Milestone.validate",
            side_effect=error if isinstance(error, MilestoneValidationError) else None,
        ),
    ):
        result = runner.invoke(app, ["query", "milestone", "001000", "1", "999"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Milestone lookup failed" in result.stderr
    assert expected_message in result.stderr
    assert "Traceback" not in result.stderr
    make_qr.assert_not_called()
