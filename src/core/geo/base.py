"""Shared map element base types and validated-construction markers."""

from __future__ import annotations

from abc import ABC

from shapely.geometry.base import BaseGeometry

# Maximum WGS84 delta (degrees) between clicked map coords and referentiel row.
COORD_TOLERANCE_DEGREES: float = 0.0001

# Only ``validate()`` and ``from_validated_summary()`` classmethods pass this token.
_VALIDATED_FACTORY_TOKEN = object()


def is_validated_construction(token: object | None) -> bool:
    """Return True when a geo object was built through a validated factory path."""
    return token is _VALIDATED_FACTORY_TOKEN


class MapElement(ABC):
    """Abstract base class for all map elements."""

    def __init__(self, id: str, geometry: BaseGeometry):
        """Initialize a map element with the given id and geometry."""
        if not isinstance(geometry, BaseGeometry):
            raise TypeError("Geometry must be a BaseGeometry")
        self._id = id
        self._geometry = geometry

    @property
    def id(self) -> str:
        """Return the id of the map element."""
        return self._id

    @property
    def geometry(self) -> BaseGeometry:
        """Return the geometry of the map element."""
        return self._geometry

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MapElement):
            return False
        return self._id == other._id and self._geometry == other._geometry

    def __hash__(self) -> int:
        return hash((self._id, self._geometry))
