"""Tests for milestone validation in core.geo.element."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core.geo.element import Milestone, Railway, clear_referentiel_pk_cache
from core.geo.exceptions import MilestoneValidationError
from core.geo.location import Location


@pytest.fixture(autouse=True)
def _clear_referentiel_cache() -> Iterator[None]:
    clear_referentiel_pk_cache()
    yield
    clear_referentiel_pk_cache()


def test_milestone_validate_returns_canonical_referentiel_coords() -> None:
    validated = Milestone.validate(
        "001+000",
        "001000",
        Location(lat=48.88533318609319, lon=2.363530409238113),
    )
    expected_line = Railway.validate(code="001000")

    assert isinstance(validated, Milestone)
    assert validated.id == "001+000"
    assert validated.geometry.y == pytest.approx(48.88533318609319)
    assert validated.geometry.x == pytest.approx(2.363530409238113)
    assert validated.line.code == "001000"
    assert validated.label == f"001+000 on {expected_line}"


def test_milestone_validate_rejects_unknown_marker() -> None:
    with pytest.raises(MilestoneValidationError, match="Unknown milestone id"):
        Milestone.validate(
            "999+999",
            "001000",
            Location(lat=0.0, lon=0.0),
        )


def test_milestone_validate_rejects_unknown_line_for_duplicate_pk() -> None:
    with pytest.raises(
        MilestoneValidationError,
        match="Unknown milestone '140\\+000' on line with code_ligne: '001306'",
    ):
        Milestone.validate(
            "140+000",
            "001306",
            Location(lat=47.758652, lon=1.935775),
        )


def test_milestone_validate_resolves_duplicate_pk_by_line() -> None:
    validated = Milestone.validate(
        "140+000",
        "590000",
        Location(lat=47.758652, lon=1.935775),
    )
    assert validated.line.code == "590000"
    assert validated.geometry.y == pytest.approx(47.758652)
    assert validated.geometry.x == pytest.approx(1.935775)


def test_milestone_validate_rejects_coord_mismatch() -> None:
    with pytest.raises(
        MilestoneValidationError,
        match="Geometry does not match referentiel for milestone",
    ):
        Milestone.validate(
            "001+000",
            "001000",
            Location(lat=48.0, lon=2.0),
        )
