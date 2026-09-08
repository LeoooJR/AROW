"""Tests for the railway query command."""

from io import StringIO
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from commands import app
from core.geo.exceptions import RailwayValidationError
from core.geo.railway import Railway

runner = CliRunner()


def _railway() -> Railway:
    return cast(
        Railway,
        SimpleNamespace(
            id="47186fe6-6665-11e3-afff-01f464e0362d",
            code="001000",
            troncon=1,
            label="Ligne de Paris-Est à Mulhouse-Ville",
            type="Ligne proprement dite",
        ),
    )


def test_railway_query_renders_metadata_and_primary_key_qr() -> None:
    """A resolved railway is rendered with all concise metadata and its QR code."""
    railway = _railway()
    qr_code = Mock(name="qr_code")

    def write_terminal(*, out: StringIO, compact: bool) -> None:
        assert compact is True
        out.write("██\n▀▀\n")

    qr_code.terminal.side_effect = write_terminal
    with (
        patch(
            "commands.query.railway.Railway.validate", return_value=railway
        ) as validate_railway,
        patch(
            "commands.query.presentation.segno.make", return_value=qr_code
        ) as make_qr,
    ):
        result = runner.invoke(app, ["query", "railway", "001000", "1"])

    assert result.exit_code == 0
    validate_railway.assert_called_once_with(code="001000", troncon=1)
    make_qr.assert_called_once_with("001000-1", micro=False)
    qr_code.terminal.assert_called_once()
    for expected in (
        "Railway target",
        "Ready",
        "Railway",
        "█",
        "47186fe6-6665-11e3-afff-01f464e0362d",
        "001000",
        "1",
        "Ligne de Paris-Est à Mulhouse-Ville",
        "Ligne proprement dite",
        "line 001000 · section 1",
    ):
        assert expected in result.stdout


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        (["query", "railway", "1000", "1"], "must contain exactly six digits"),
        (["query", "railway", "ABCDEF", "1"], "must contain exactly six digits"),
        (
            ["query", "railway", "001000", "0"],
            "section must be a positive integer",
        ),
        (
            ["query", "railway", "001000", "-1"],
            "section must be a positive integer",
        ),
    ],
)
def test_railway_query_rejects_invalid_arguments(
    arguments: list[str], expected_error: str
) -> None:
    """The railway key must use a six-digit code and positive section."""
    result = runner.invoke(app, arguments, terminal_width=120)

    assert result.exit_code == 2
    normalized_error = " ".join(result.stderr.replace("│", " ").split())
    assert expected_error in normalized_error


def test_railway_query_reports_unknown_railway_without_generating_qr() -> None:
    """Expected lookup failures are concise and stop before presentation."""
    error = RailwayValidationError("Unknown railway code_ligne: '999999'")

    with (
        patch("commands.query.presentation.segno.make") as make_qr,
        patch("commands.query.railway.Railway.validate", side_effect=error),
    ):
        result = runner.invoke(app, ["query", "railway", "999999", "1"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Railway lookup failed" in result.stderr
    assert "Unknown railway code_ligne: '999999'" in result.stderr
    assert "Traceback" not in result.stderr
    make_qr.assert_not_called()
