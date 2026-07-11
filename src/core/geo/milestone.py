"""Milestone map element and conversion helpers.

Milestone participates in four distinct conversion paths. Keep them separate:

1. **Referentiel validation** — ``validate()`` queries ``referentiel_pk_gps`` and is
   the authoritative check. Use on worker threads and when rebuilding from disk via
   ``deserialize()``.
2. **Persistence** — ``serialize()`` / ``deserialize()`` implement the ``Payload``
   contract for simulation JSON (nested under ``Location``). ``deserialize()`` always
   re-validates through ``validate()`` so restored data matches the referentiel.
3. **Trusted main-thread rebuild** — ``from_validated_summary()`` reconstructs a
   milestone from scalars already validated elsewhere; no database lookup.
4. **Controller bus bridge** — ``from_validated_payload()`` / ``to_validated_payload()``
   convert between domain objects and ``SimulationLocationValidatedPayload`` so geo
   types never cross the controller boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pandas as pd
from shapely.geometry import Point

from core.geo.base import (
    _VALIDATED_FACTORY_TOKEN,
    COORD_TOLERANCE_DEGREES,
    MapElement,
    is_validated_construction,
)
from core.geo.datasets import DatasetManager
from core.geo.exceptions import MilestoneValidationError
from core.geo.geometry import serialize_geometry
from core.geo.railway import Railway, normalize_code_ligne
from core.payload import Payload

if TYPE_CHECKING:
    from core.signals import SimulationLocationValidatedPayload


class Milestone(MapElement, Payload):
    """A milestone on the map."""

    def __init__(
        self,
        km: int,
        line: Railway,
        type: Literal["Kilometer", "Hectometer"],
        label: str,
        geometry: Point,
        *,
        _validated_token: object | None = None,
    ):
        """
        Initialize a milestone with the given km, line, type, label and geometry.

        Do not use this constructor directly; use ``Milestone.validate()`` instead.
        """
        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")
        if not isinstance(line, Railway):
            raise TypeError("Line must be a Railway")
        milestone_id = f"{line.code}-{line.troncon}-{km}"
        super().__init__(milestone_id, geometry)
        self._id = milestone_id
        self._km = km
        self._line = line
        self._type = type
        self._label = label
        self._is_validated = is_validated_construction(_validated_token)

    @property
    def is_validated(self) -> bool:
        """Return True when the milestone was created by ``Milestone.validate``."""
        return self._is_validated

    @property
    def km(self) -> int:
        """Return the kilometer of the milestone."""
        return self._km

    @property
    def line(self) -> Railway:
        """Return the line of the milestone."""
        return self._line

    @property
    def type(self) -> Literal["Kilometer", "Hectometer"]:
        """Return the type of the milestone."""
        return self._type

    @property
    def label(self) -> str:
        """Return the label of the milestone."""
        return self._label

    def _is_on_line(self, line: Railway) -> bool:
        """Return True if the milestone is on the given line."""
        return self.geometry.dwithin(line.geometry, COORD_TOLERANCE_DEGREES)

    # --- Referentiel validation (worker / disk restore) ---

    @classmethod
    def validate(
        cls, km: int, line: Railway, geometry: Point | None = None
    ) -> Milestone:
        """Resolve and validate a map milestone against ``referentiel_pk_gps``.

        Authoritative validation path: queries the PK referential, checks coordinates
        when provided, and marks the result as validated. Use from async geo work and
        from ``deserialize()`` when loading persisted simulation metadata.
        """
        if not isinstance(km, int):
            raise TypeError("Kilometer must be an integer")
        if km <= 0:
            raise MilestoneValidationError("Kilometer must be a positive integer")

        if geometry is not None:
            if not isinstance(geometry, Point):
                raise TypeError("Geometry must be a Point")
            if geometry.x < -180 or geometry.x > 180:
                raise MilestoneValidationError(
                    "Geometry x coordinate must be between -180 and 180"
                )
            if geometry.y < -90 or geometry.y > 90:
                raise MilestoneValidationError(
                    "Geometry y coordinate must be between -90 and 90"
                )

        if not isinstance(line, Railway):
            raise TypeError("Line must be a Railway")
        if not line.is_validated:
            raise MilestoneValidationError(
                "Railway must be validated with Railway.validate()"
            )

        code_normalized = normalize_code_ligne(line.code)
        result = DatasetManager.query(
            id="referentiel_pk_gps",
            sql="""
            SELECT * FROM kilometric_points
            WHERE code_ligne = ?
            AND rg_troncon = ?
            AND km = ?
            """,
            code_ligne=code_normalized,
            rg_troncon=line.troncon,
            km=km,
        )

        if result.empty:
            raise MilestoneValidationError(f"Unknown milestone: {line.id!r} {km}")

        if len(result.index) > 1:
            raise MilestoneValidationError(f"Multiple matches for {line.id!r} {km}")

        row: pd.Series = result.iloc[0]
        referentiel_geometry = Point(row["geometry"].x, row["geometry"].y)

        if geometry is not None:
            if referentiel_geometry.distance(geometry) > COORD_TOLERANCE_DEGREES:
                raise MilestoneValidationError(
                    f"Geometry does not match referentiel for milestone {line.id!r} {km}"
                )

        referentiel_label = str(row["label"])
        milestone = cls(
            km=km,
            line=line,
            type="Kilometer",
            label=referentiel_label,
            geometry=referentiel_geometry,
            _validated_token=_VALIDATED_FACTORY_TOKEN,
        )

        if milestone._is_on_line(line):
            return milestone
        raise MilestoneValidationError(
            f"Milestone {milestone._id} is not on line {line}"
        )

    # --- Trusted main-thread rebuild (no referentiel lookup) ---

    @classmethod
    def from_validated_summary(
        cls,
        *,
        km: int,
        line: Railway,
        type: Literal["Kilometer", "Hectometer"],
        label: str,
        lat: float,
        lon: float,
    ) -> Milestone:
        """Rebuild a validated milestone on the main thread without referentiel lookup.

        Expects scalars that were already validated (e.g. from a prior ``validate()``
        call or from a trusted ``SimulationLocationValidatedPayload``). Does not hit
        the database; only suitable on the Qt main thread.
        """
        return cls(
            km=km,
            line=line,
            type=type,
            label=label,
            geometry=Point(lon, lat),
            _validated_token=_VALIDATED_FACTORY_TOKEN,
        )

    # --- Controller bus bridge (scalar payload, no domain in controller) ---

    @classmethod
    def from_validated_payload(
        cls, payload: SimulationLocationValidatedPayload
    ) -> Milestone:
        """Rebuild a validated milestone from a controller-safe scalar payload.

        Converts ``SimulationLocationValidatedPayload`` into domain objects via
        ``from_validated_summary()``. Used when applying validated location results
        on the main thread without re-running referentiel validation.
        """
        railway = Railway.from_validated_summary(
            id=payload.line_id,
            code=payload.line_code,
            troncon=payload.line_troncon,
            type=payload.line_type,
            label=payload.line_label,
            geometry_wkb_b64=payload.line_geometry_wkb_b64,
        )
        return cls.from_validated_summary(
            km=payload.km,
            line=railway,
            type=payload.milestone_type,
            label=payload.label,
            lat=payload.lat,
            lon=payload.lon,
        )

    @staticmethod
    def to_validated_payload(
        *,
        simulation_id: str,
        milestone: Milestone,
        line: Railway,
    ) -> SimulationLocationValidatedPayload:
        """Build a scalar validated payload from worker-thread domain objects.

        Flattens a validated ``Milestone`` and ``Railway`` into
        ``SimulationLocationValidatedPayload`` for core-bus emission. Controllers
        consume the payload without importing geo domain types.
        """
        from core.signals import SimulationLocationValidatedPayload

        geometry_b64 = serialize_geometry(line.geometry, json_compatible=True)
        return SimulationLocationValidatedPayload(
            simulation_id=simulation_id,
            lat=milestone.geometry.y,
            lon=milestone.geometry.x,
            km=milestone.km,
            label=milestone.label,
            milestone_type=milestone.type,
            line_id=line.id,
            line_code=line.code,
            line_troncon=line.troncon,
            line_type=line.type,
            line_label=line.label,
            line_geometry_wkb_b64=str(geometry_b64),
        )

    # --- Persistence (simulation JSON under Location) ---

    def serialize(self, **kwargs) -> dict[str, object]:
        """Serialize milestone fields for simulation metadata persistence."""
        return {
            "km": self._km,
            "line": self._line.serialize(**kwargs),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Milestone:
        """Restore a milestone from simulation metadata and re-validate against referentiel."""
        line_payload = payload.get("line")
        if not isinstance(line_payload, dict):
            raise ValueError("Milestone payload line must be a dictionary")
        line = Railway.deserialize(line_payload, **kwargs)
        milestone_km = payload.get("km")
        if not isinstance(milestone_km, int):
            raise ValueError("Milestone payload km must be an integer")
        return cls.validate(km=milestone_km, line=line)

    def __repr__(self) -> str:
        return f"{self._km} on {self._line}"
