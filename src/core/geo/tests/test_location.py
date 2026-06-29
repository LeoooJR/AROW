"""Tests for core.geo.location."""

from __future__ import annotations

from typing import cast

from core.geo.location import Location


def test_location_payload_round_trip() -> None:
    location = Location(lat=48.885333, lon=2.363530, label="001+000 / 001000-1")
    payload = location.to_payload()
    restored = Location.from_payload(cast(dict[str, object], payload))
    assert restored == location
