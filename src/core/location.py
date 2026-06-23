from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, cast


@dataclass(frozen=True, unsafe_hash=True)
class Location:
    lat: float = field(
        metadata={"description": "The latitude of the location"}, default=0.0
    )
    lon: float = field(
        metadata={"description": "The longitude of the location"}, default=0.0
    )
    label: Optional[str] = field(
        metadata={"description": "The label of the location"}, default=None
    )

    def to_payload(self) -> dict[str, float | str | None]:
        """
        Convert the location to a payload.
        """
        return {
            "lat": self.lat,
            "lon": self.lon,
            "label": self.label,
        }

    @staticmethod
    def from_payload(payload: dict[str, object]) -> Location:
        """
        Create a location from a payload.
        """
        label = payload.get("label")
        return Location(
            lat=float(cast(float | int | str, payload["lat"])),
            lon=float(cast(float | int | str, payload["lon"])),
            label=None if label is None else str(label),
        )
