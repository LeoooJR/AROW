"""Tests for milestone validation in core.geo.milestone."""

from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point

from core.geo.exceptions import MilestoneValidationError
from core.geo.milestone import Milestone
from core.geo.railway import Railway


def test_milestone_validate_returns_canonical_referentiel_coords() -> None:
    line = Railway.validate(code="001000", troncon=1)
    validated = Milestone.validate(
        km=1,
        line=line,
        geometry=Point(2.363530409238113, 48.88533318609319),
    )

    assert isinstance(validated, Milestone)
    assert validated.is_validated
    assert validated.id == "001000-1-1"
    assert validated.geometry.y == pytest.approx(48.88533318609319)
    assert validated.geometry.x == pytest.approx(2.363530409238113)
    assert validated.line.code == "001000"
    assert validated.line.troncon == line.troncon
    assert validated.label == "001+000"


def test_milestone_validate_rejects_unknown_marker() -> None:
    line = Railway.validate(code="001000", troncon=1)
    with pytest.raises(MilestoneValidationError, match="Unknown milestone"):
        Milestone.validate(
            km=999,
            line=line,
            geometry=Point(0.0, 0.0),
        )


def test_milestone_validate_rejects_unknown_line_for_duplicate_pk() -> None:
    line = Railway.validate(code="001306", troncon=1)
    with pytest.raises(
        MilestoneValidationError,
        match="Unknown milestone:",
    ):
        Milestone.validate(
            km=140,
            line=line,
            geometry=Point(1.935775, 47.758652),
        )


def test_milestone_validate_resolves_duplicate_pk_by_line() -> None:
    line = Railway.validate(code="590000", troncon=2)
    validated = Milestone.validate(
        km=140,
        line=line,
        geometry=Point(1.935775, 47.758652),
    )
    assert validated.line.code == "590000"
    assert validated.line.troncon == 2
    assert validated.geometry.y == pytest.approx(47.758652)
    assert validated.geometry.x == pytest.approx(1.935775)


def test_milestone_validate_rejects_coord_mismatch() -> None:
    line = Railway.validate(code="001000", troncon=1)
    with pytest.raises(
        MilestoneValidationError,
        match="Geometry does not match referentiel for milestone",
    ):
        Milestone.validate(
            km=1,
            line=line,
            geometry=Point(2.0, 48.0),
        )


def test_milestone_validate_rejects_unvalidated_railway() -> None:
    validated_line = Railway.validate(code="001000", troncon=1)
    unvalidated_line = Railway(
        id=validated_line.id,
        code=validated_line.code,
        troncon=validated_line.troncon,
        type=validated_line.type,
        label=validated_line.label,
        geometry=validated_line.geometry,
    )
    assert not unvalidated_line.is_validated

    with pytest.raises(
        MilestoneValidationError,
        match="Railway must be validated with Railway.validate\\(\\)",
    ):
        Milestone.validate(
            km=1,
            line=unvalidated_line,
            geometry=Point(2.363530409238113, 48.88533318609319),
        )


def test_milestone_direct_constructor_is_not_validated() -> None:
    line = Railway.validate(code="001000", troncon=1)
    milestone = Milestone(
        km=1,
        line=line,
        type="Kilometer",
        label="001+000",
        geometry=Point(2.363530409238113, 48.88533318609319),
    )
    assert not milestone.is_validated


def test_railway_validate_marks_railway_as_validated() -> None:
    line = Railway.validate(code="001000", troncon=1)
    assert line.is_validated
    assert isinstance(line.geometry, (LineString,))
