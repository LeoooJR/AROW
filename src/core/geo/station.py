"""Station map element."""

from __future__ import annotations

from shapely.geometry import Point

from core.geo.base import MapElement
from core.geo.geometry import deserialize_geometry, serialize_geometry
from core.payload import Payload


class Station(MapElement, Payload):
    """A station on the map."""

    def __init__(self, id: str, geometry: Point):
        """Initialize a station with the given id and geometry."""
        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")
        super().__init__(id, geometry)

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "id": self.id,
            "geometry": serialize_geometry(self.geometry, **kwargs),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Station:
        station_id = payload["id"]
        if not isinstance(station_id, str):
            raise ValueError("Station payload id must be a string")
        return cls(
            id=station_id,
            geometry=deserialize_geometry(payload["geometry"]),
        )
