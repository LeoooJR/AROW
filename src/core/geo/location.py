"""Location domain types and referentiel marker validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from core.geo.element import Milestone
from core.payload import Payload


@dataclass(frozen=True, unsafe_hash=True)
class Location(Payload):
    """Location."""

    lat: float = field(
        metadata={"description": "The latitude of the location"}, default=0.0
    )
    lon: float = field(
        metadata={"description": "The longitude of the location"}, default=0.0
    )
    poi: Milestone | None = field(
        metadata={"description": "The point of interest at the given location"},
        default=None,
    )

    def is_default(self) -> bool:
        """Return True if the location is the default location."""
        return self.lat == 0.0 and self.lon == 0.0 and self.poi is None

    def to_payload(self, **kwargs) -> dict[str, object]:
        """Convert the location to a payload."""
        return {
            "lat": self.lat,
            "lon": self.lon,
            "poi": (self.poi.to_payload(**kwargs) if self.poi is not None else None),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object], **kwargs) -> Location:
        """Create a location from a payload."""
        poi_payload = payload.get("poi")
        poi: Milestone | None = None
        if isinstance(poi_payload, dict):
            poi = Milestone.from_payload(
                cast(dict[str, object], poi_payload),
                **kwargs,
            )
        return cls(
            lat=float(cast(float | int | str, payload.get("lat", 0.0))),
            lon=float(cast(float | int | str, payload.get("lon", 0.0))),
            poi=poi,
        )
