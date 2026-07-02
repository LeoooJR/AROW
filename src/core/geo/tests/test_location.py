"""Tests for core.geo.location."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from shapely.geometry import Point

from core.geo.element import Milestone, clear_referentiel_pk_cache
from core.geo.location import Location


@pytest.fixture(autouse=True)
def _clear_referentiel_cache() -> Iterator[None]:
    clear_referentiel_pk_cache()
    yield
    clear_referentiel_pk_cache()


def test_location_payload_round_trip_without_poi() -> None:
    location = Location(lat=48.885333, lon=2.363530, poi=None)
    payload = location.to_payload()
    restored = Location.from_payload(cast(dict[str, object], payload))
    assert restored == location


def test_location_payload_round_trip_with_milestone() -> None:
    milestone = Milestone.validate(
        "001+000",
        "001000",
        Point(2.363530409238113, 48.88533318609319),
    )
    location = Location(
        lat=48.88533318609319,
        lon=2.363530409238113,
        poi=milestone,
    )
    payload = location.to_payload()
    restored = Location.from_payload(cast(dict[str, object], payload))
    assert restored.lat == location.lat
    assert restored.lon == location.lon
    assert restored.poi is not None
    assert restored.poi.id == milestone.id
    assert restored.poi.label == milestone.label
