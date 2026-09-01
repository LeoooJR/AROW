"""Tests for the milestone query command."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from shapely.geometry import Point
from typer.testing import CliRunner

from commands import app
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError

runner = CliRunner()


def _railway() -> SimpleNamespace:
    return SimpleNamespace(
        id="47186fe6-6665-11e3-afff-01f464e0362d",
        code="001000",
        troncon=1,
        label="Ligne de Paris-Est à Mulhouse-Ville",
        type="Ligne proprement dite",
    )


def _milestone(line: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id="001000-1-1",
        label="001+000",
        km=1,
        type="Kilometer",
        geometry=Point(2.363530409238113, 48.88533318609319),
        line=line,
    )


def test_milestone_query_renders_complete_metadata_card() -> None:
    """A resolved milestone is rendered with milestone, railway, and source data."""
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
        "Reference data",
        "001000-1-1",
        "001+000",
        "Kilometer",
        "48.885333",
        "2.363530",
        "47186fe6-6665-11e3-afff-01f464e0362d",
        "001000",
        "Ligne de Paris-Est à Mulhouse-Ville",
        "Ligne proprement dite",
        "referentiel_pk_gps",
        "lignes-par-type",
    ):
        assert expected in result.stdout


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
