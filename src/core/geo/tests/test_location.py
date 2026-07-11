"""Tests for core.geo.location."""

from __future__ import annotations

from typing import cast

import pytest
from shapely.geometry import Point

from core.geo.location import Location
from core.geo.milestone import Milestone
from core.geo.railway import Railway


def test_location_payload_round_trip_without_poi() -> None:
    location = Location(lat=48.885333, lon=2.363530, poi=None)
    payload = location.serialize()
    restored = Location.deserialize(cast(dict[str, object], payload))
    assert restored == location


def test_location_payload_round_trip_with_milestone() -> None:
    line = Railway.validate(code="001000", troncon=1)
    milestone = Milestone.validate(
        km=1,
        line=line,
        geometry=Point(2.363530409238113, 48.88533318609319),
    )
    location = Location(
        lat=48.88533318609319,
        lon=2.363530409238113,
        poi=milestone,
    )
    payload = location.serialize()
    restored = Location.deserialize(cast(dict[str, object], payload))
    assert restored.lat == location.lat
    assert restored.lon == location.lon
    assert restored.poi is not None
    assert restored.poi.is_validated
    assert restored.poi.id == milestone.id
    assert restored.poi.label == milestone.label
