"""Tests for milestone validation in core.geo.element."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core.geo.element import Milestone, clear_referentiel_pk_cache
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
        "001000-1",
        Location(lat=48.88533318609319, lon=2.363530409238113),
    )
    assert isinstance(validated, Milestone)
    assert validated.id == "001+000"
    assert validated.location.lat == pytest.approx(48.88533318609319)
    assert validated.location.lon == pytest.approx(2.363530409238113)
    assert validated.line == "001000-1"
    assert validated.label == "001+000 / 001000-1"


def test_milestone_validate_rejects_unknown_marker() -> None:
    with pytest.raises(MilestoneValidationError, match="Unknown milestone id"):
        Milestone.validate(
            "999+999",
            "001000-1",
            Location(lat=0.0, lon=0.0),
        )


def test_milestone_validate_rejects_unknown_line_for_duplicate_pk() -> None:
    with pytest.raises(MilestoneValidationError, match="Unknown milestone line"):
        Milestone.validate(
            "140+000",
            "unknown-line",
            Location(lat=47.758652, lon=1.935775),
        )


def test_milestone_validate_resolves_duplicate_pk_by_line() -> None:
    validated = Milestone.validate(
        "140+000",
        "590000-2",
        Location(lat=47.758652, lon=1.935775),
    )
    assert validated.line == "590000-2"
    assert validated.location.lat == pytest.approx(47.758652)
    assert validated.location.lon == pytest.approx(1.935775)


def test_milestone_validate_rejects_coord_mismatch() -> None:
    with pytest.raises(
        MilestoneValidationError,
        match="Clicked coordinates do not match referentiel",
    ):
        Milestone.validate(
            "001+000",
            "001000-1",
            Location(lat=48.0, lon=2.0),
        )
