"""Tests for core.geo.location."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest

from core.geo.location import (
    Location,
    ValidatedMarkerLocation,
    clear_referentiel_pk_cache,
    validate_marker_location,
)


@pytest.fixture(autouse=True)
def _clear_referentiel_cache() -> Iterator[None]:
    clear_referentiel_pk_cache()
    yield
    clear_referentiel_pk_cache()


def test_location_payload_round_trip() -> None:
    location = Location(lat=48.885333, lon=2.363530, label="001+000 / 001000-1")
    payload = location.to_payload()
    restored = Location.from_payload(cast(dict[str, object], payload))
    assert restored == location


def test_validate_marker_location_returns_canonical_referentiel_coords() -> None:
    validated = validate_marker_location(
        "001+000",
        "001000-1",
        48.88533318609319,
        2.363530409238113,
    )
    assert isinstance(validated, ValidatedMarkerLocation)
    assert validated.marker_id == "001+000"
    assert validated.lat == pytest.approx(48.88533318609319)
    assert validated.lon == pytest.approx(2.363530409238113)
    assert validated.line == "001000-1"
    assert validated.label == "001+000 / 001000-1"


def test_validate_marker_location_rejects_unknown_marker() -> None:
    with pytest.raises(ValueError, match="Unknown milestone marker id"):
        validate_marker_location("999+999", "001000-1", 0.0, 0.0)


def test_validate_marker_location_rejects_unknown_line_for_duplicate_pk() -> None:
    with pytest.raises(ValueError, match="Unknown milestone line"):
        validate_marker_location(
            "140+000",
            "unknown-line",
            47.758652,
            1.935775,
        )


def test_validate_marker_location_resolves_duplicate_pk_by_line() -> None:
    validated = validate_marker_location(
        "140+000",
        "590000-2",
        47.758652,
        1.935775,
    )
    assert validated.line == "590000-2"
    assert validated.lat == pytest.approx(47.758652)
    assert validated.lon == pytest.approx(1.935775)


def test_validate_marker_location_rejects_coord_mismatch() -> None:
    with pytest.raises(
        ValueError, match="Clicked coordinates do not match referentiel"
    ):
        validate_marker_location(
            "001+000",
            "001000-1",
            48.0,
            2.0,
        )
