from __future__ import annotations

import base64
import re
from abc import ABC
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast

import geopandas
import pandas as pd
from shapely import from_wkb
from shapely.geometry import LineString, MultiLineString, Point
from shapely.geometry.base import BaseGeometry

from core.geo.datasets import DatasetManager
from core.geo.exceptions import MilestoneValidationError, RailwayValidationError
from core.payload import Payload

# Maximum WGS84 delta (degrees) between clicked map coords and referentiel row.
_COORD_TOLERANCE_DEGREES: float = 0.0001

# Internal factory marker: only validate() classmethods pass this token.
_VALIDATED_FACTORY_TOKEN = object()


def _serialize_geometry(geometry: BaseGeometry, **kwargs: object) -> bytes | str:
    """Serialize geometry for persistence; base64 when writing JSON metadata."""
    wkb = geometry.wkb
    if kwargs.get("json_compatible", False):
        return base64.b64encode(wkb).decode("ascii")
    return wkb


def _deserialize_geometry(raw: object) -> BaseGeometry:
    """Restore geometry from a payload field (raw WKB bytes or base64 text)."""
    if isinstance(raw, str):
        return from_wkb(base64.b64decode(raw))
    return from_wkb(cast(bytes, raw))


@dataclass(frozen=True, slots=True)
class _ValidatedRailwaySnapshot:
    """Pre-aggregated railway metadata and segment geometry from lignes-par-type."""

    id: str
    code: str
    troncon: int
    type: str
    label: str
    geometry: LineString | MultiLineString


@lru_cache(maxsize=1)
def _lignes_par_type_dataset() -> geopandas.GeoDataFrame:
    """Load and normalize the lignes-par-type dataset once per process."""
    dataset: geopandas.GeoDataFrame = DatasetManager.read("lignes-par-type")
    return dataset


def _normalize_lookup_key(value: object) -> str | None:
    """Return a stripped string lookup key, or None when the value is missing."""
    if pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _railway_snapshot_from_segment(
    row: pd.Series,
) -> _ValidatedRailwaySnapshot:
    """Build one railway snapshot from a single lignes-par-type segment row."""
    id_key = _normalize_lookup_key(row["idgaia"])
    code_key = _normalize_lookup_key(row["code_ligne"])
    if id_key is None or code_key is None:
        raise ValueError("Missing railway lookup key in lignes-par-type row")
    return _ValidatedRailwaySnapshot(
        id=id_key,
        code=code_key,
        troncon=int(row["rg_troncon"]),
        type=row["type_ligne"],
        label=row["lib_ligne"],
        geometry=row["geometry"],
    )


@lru_cache(maxsize=1)
def _railway_lookup_indexes() -> tuple[
    dict[str, dict[int, _ValidatedRailwaySnapshot]],
    dict[str, dict[int, _ValidatedRailwaySnapshot]],
]:
    """Build O(1) railway lookup indexes keyed by SNCF Gaïa id and numeric line code."""
    referentiel = _lignes_par_type_dataset()
    by_idgaia: dict[str, dict[int, _ValidatedRailwaySnapshot]] = (
        {}
    )  # Keyed by SNCF Gaïa id and troncon.
    by_code_ligne: dict[str, dict[int, _ValidatedRailwaySnapshot]] = (
        {}
    )  # Keyed by numeric line code and troncon.

    idgaia_keys = referentiel["idgaia"].unique().map(_normalize_lookup_key)
    for lookup_key in idgaia_keys:
        if lookup_key is None:
            continue
        result: pd.DataFrame = referentiel.loc[referentiel["idgaia"] == lookup_key]
        for (
            _index,
            row,
        ) in (
            result.iterrows()
        ):  # Iterate over all segments (troncons) for the same railway.
            by_idgaia.setdefault(lookup_key, {})[int(row["rg_troncon"])] = (
                _railway_snapshot_from_segment(row)
            )

    code_keys = referentiel["code_ligne"].unique().map(_normalize_lookup_key)
    for lookup_key in code_keys:
        if lookup_key is None:
            continue
        code_result: pd.DataFrame = referentiel.loc[
            referentiel["code_ligne"] == lookup_key
        ]
        for (
            _index,
            row,
        ) in (
            code_result.iterrows()
        ):  # Iterate over all segments (troncons) for the same railway.
            by_code_ligne.setdefault(lookup_key, {})[int(row["rg_troncon"])] = (
                _railway_snapshot_from_segment(row)
            )

    return by_idgaia, by_code_ligne


def _normalize_code_ligne(value: object) -> str:
    """Normalize numeric line codes to six digits for referentiel matching."""
    normalized = str(value).strip()
    if normalized.isdigit():
        return normalized.zfill(6)
    return normalized


def clear_lignes_par_type_cache() -> None:
    """Clear the cached lignes-par-type dataset (for tests)."""
    _lignes_par_type_dataset.cache_clear()
    _railway_lookup_indexes.cache_clear()


class MapElement(ABC):
    """
    Abstract base class for all map elements.
    """

    def __init__(self, id: str, geometry: BaseGeometry):
        """
        Initialize a map element with the given id and geometry.

        Args:
            id: The id of the map element.
            geometry: The geometry of the map element.
        """
        if not isinstance(geometry, BaseGeometry):
            raise TypeError("Geometry must be a BaseGeometry")
        self._id = id
        self._geometry = geometry

    @property
    def id(self) -> str:
        """
        Return the id of the map element.
        """
        return self._id

    @property
    def geometry(self) -> BaseGeometry:
        """
        Return the geometry of the map element.
        """
        return self._geometry

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MapElement):
            return False
        return self._id == other._id and self._geometry == other._geometry

    def __hash__(self) -> int:
        return hash((self._id, self._geometry))


class Station(MapElement, Payload):
    """
    A station on the map.
    """

    def __init__(self, id: str, geometry: Point):
        """
        Initialize a station with the given id and geometry.

        Args:
            id: The id of the station.
            geometry: The geometry of the station. Must be a Point.

        Raises:
            TypeError: If the geometry is not a Point.
        """
        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")
        super().__init__(
            id,
            geometry,
        )

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "id": self.id,
            "geometry": _serialize_geometry(self.geometry, **kwargs),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Station:
        station_id = payload["id"]
        if not isinstance(station_id, str):
            raise ValueError("Station payload id must be a string")
        return cls(
            id=station_id,
            geometry=_deserialize_geometry(payload["geometry"]),
        )


class Milestone(MapElement, Payload):
    """
    A milestone on the map.
    """

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

        Do not use this constructor directly, use Milestone.validate() instead.

        Args:
            km: The kilometer of the milestone.
            line: The line of the milestone. Must be a Railway.
            type: The type of the milestone (e.g Kilometer, Hectomètre, etc.).
            label: The label of the milestone (e.g "25+000").
            geometry: The geometry of the milestone. Must be a Point.

        Raises:
            TypeError: If the geometry is not a Point.
            RailwayValidationError: If the line is not a valid railway.
        """
        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")
        if not isinstance(line, Railway):
            raise TypeError("Line must be a Railway")
        _id = f"{line.code}-{line.troncon}-{km}"
        super().__init__(
            _id,
            geometry,
        )
        self._id = _id
        self._km = km
        self._line = line
        self._type = type
        self._label = label
        self._is_validated = _validated_token is _VALIDATED_FACTORY_TOKEN

    @property
    def is_validated(self) -> bool:
        """Return True when the milestone was created by ``Milestone.validate``."""
        return self._is_validated

    @property
    def km(self) -> int:
        """
        Return the kilometer of the milestone.
        """
        return self._km

    @property
    def line(self) -> Railway:
        """
        Return the line of the milestone.
        """
        return self._line

    @property
    def type(self) -> str:
        """
        Return the type of the milestone.
        """
        return self._type

    @property
    def label(self) -> str:
        """
        Return the label of the milestone.
        """
        return self._label

    def _is_on_line(self, line: Railway) -> bool:
        """
        Return True if the milestone is on the given line, False otherwise.
        """
        return self.geometry.dwithin(line.geometry, _COORD_TOLERANCE_DEGREES)

    @classmethod
    def validate(
        cls, km: int, line: Railway, geometry: Point | None = None
    ) -> Milestone:
        """Resolve and validate a map milestone against ``referentiel_pk_gps``.

        Args:
            km: The kilometer of the milestone.
            line: The line of the milestone. Must be a valid Railway initialized with Railway.validate().
            geometry: The geometry of the milestone. Must be a Point. Will be validated if provided.

        Returns:
            Validated milestone.

        Raises:
            MilestoneValidationError: When the milestone is unknown or location diverges from referentiel.
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

        code_normalized = _normalize_code_ligne(line.code)
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

        # Result is a single row DataFrame, convert to Series for consistent indexing.
        row: pd.Series = result.iloc[0]

        referentiel_geometry = Point(row["geometry"].x, row["geometry"].y)

        if geometry is not None:
            if referentiel_geometry.distance(geometry) > _COORD_TOLERANCE_DEGREES:
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
        else:
            raise MilestoneValidationError(
                f"Milestone {milestone._id} is not on line {line}"
            )

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "km": self._km,
            "line": self._line.serialize(**kwargs),
            "type": self._type,
            "label": self._label,
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Milestone:
        line_payload = payload.get("line")
        if not isinstance(line_payload, dict):
            raise ValueError("Milestone payload line must be a dictionary")
        line = Railway.deserialize(line_payload, **kwargs)
        milestone_km = payload.get("km")
        if not isinstance(milestone_km, int):
            raise ValueError("Milestone payload km must be an integer")
        milestone = cls.validate(
            km=milestone_km,
            line=line,
        )
        return milestone

    def __repr__(self) -> str:
        return f"{self._km} on {self._line}"


class Railway(MapElement, Payload):
    """
    A railway on the map.
    """

    def __init__(
        self,
        id: str,
        code: str,
        troncon: int,
        type: str,
        label: str,
        geometry: LineString | MultiLineString,
        *,
        _validated_token: object | None = None,
    ):
        """
        Initialize a railway with the given id, code, type and geometry.
        Do not use this constructor directly, use Railway.validate() instead.

        Args:
            id: The id of the railway.
            code: The code of the railway.
            troncon: The troncon of the railway.
            type: The type of the railway.
            label: The label of the railway.
            geometry: The geometry of the railway. Must be a LineString or MultiLineString.

        Raises:
            TypeError: If the geometry is not a LineString or MultiLineString.
        """
        if not isinstance(geometry, (LineString, MultiLineString)):
            raise TypeError("Geometry must be a LineString or MultiLineString")
        super().__init__(id, geometry)
        self._code = code
        self._troncon = troncon
        self._type = type
        self._label = label
        self._is_validated = _validated_token is _VALIDATED_FACTORY_TOKEN

    @property
    def is_validated(self) -> bool:
        """Return True when the railway was created by ``Railway.validate``."""
        return self._is_validated

    @property
    def code(self) -> str:
        """
        Return the code of the railway.
        """
        return self._code

    @property
    def troncon(self) -> int:
        """
        Return the troncon of the railway.
        """
        return self._troncon

    @property
    def type(self) -> str:
        """
        Return the type of the railway.
        """
        return self._type

    @property
    def label(self) -> str:
        """
        Return the label of the railway.
        """
        return self._label

    @staticmethod
    def is_idgaia(id: str) -> bool:
        """
        Return True if the id is a valid SNCF Gaïa line identifier, False otherwise.
        """
        return (
            re.match(
                r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                id,
            )
            is not None
        )

    @staticmethod
    def is_code_ligne(code: str) -> bool:
        """
        Return True if the code is a valid numeric line code, False otherwise.
        """
        return re.match(r"^\d{6}$", code) is not None

    @staticmethod
    def resolve_line_identifier_type(
        identifier: str,
    ) -> Literal["idgaia", "code_ligne"]:
        """
        Resolve the line identifier type from the given identifier.
        """
        if Railway.is_idgaia(identifier):
            return "idgaia"
        elif Railway.is_code_ligne(identifier):
            return "code_ligne"
        else:
            raise ValueError(f"Invalid line identifier: {identifier!r}")

    @classmethod
    def validate(
        cls,
        id: str | None = None,
        code: str | None = None,
        troncon: int | None = None,
        type: str | None = None,
    ) -> Railway:
        """Resolve and validate a map railway against ``lignes-par-type``. At least one of the id or code must be provided.

        Args:
            id: SNCF Gaïa line identifier (UUID). Must be provided if numeric line code is not provided or unknown.
            code: Numeric line code (6 digits). Must be provided if SNCF Gaïa line identifier is not provided or unknown.
            troncon: The troncon of the railway.
            type: Line category (e.g. principale, raccordement).

        Returns:
            Validated railway.

        Raises:
            RailwayValidationError: When the railway is unknown or location diverges from referentiel.
        """
        lookup_key_name = (
            None  # The name of the lookup key to use (idgaia or code_ligne)
        )
        normalized_lookup_key = (
            None  # The normalized lookup key to use (idgaia or code_ligne)
        )
        if id is None and code is None:
            raise RailwayValidationError(
                "At least one of the id or code must be provided"
            )

        if id is not None:
            normalized_id = str(id).strip()
            if not normalized_id:
                raise RailwayValidationError("Railway id must not be empty")
            lookup_key_name = "idgaia"
            normalized_lookup_key = normalized_id
        elif code is not None:
            normalized_code = str(code).strip()
            if not normalized_code:
                raise RailwayValidationError("Railway code must not be empty")
            lookup_key_name = "code_ligne"
            normalized_lookup_key = normalized_code

        if lookup_key_name is None or normalized_lookup_key is None:
            raise RailwayValidationError(
                "At least one of the id or code must be provided"
            )

        if troncon is not None:
            normalized_troncon = int(troncon)
            if normalized_troncon <= 0:
                raise RailwayValidationError(
                    "Railway troncon must be a positive integer"
                )
        else:
            raise RailwayValidationError("Railway troncon must be provided")

        if type is not None:
            normalized_type = str(type).strip()
            if not normalized_type:
                raise RailwayValidationError("Railway type must not be empty")

        by_idgaia, by_code_ligne = _railway_lookup_indexes()
        if lookup_key_name == "idgaia":
            segments = by_idgaia.get(normalized_lookup_key)
        else:
            segments = by_code_ligne.get(normalized_lookup_key)
        if segments is None:
            raise RailwayValidationError(
                f"Unknown railway {lookup_key_name}: {normalized_lookup_key!r}"
            )
        snapshot = segments.get(normalized_troncon)
        if snapshot is None:
            raise RailwayValidationError(
                f"Unknown railway {lookup_key_name}: {normalized_lookup_key!r}"
            )

        return cls(
            id=snapshot.id,
            code=snapshot.code,
            troncon=snapshot.troncon,
            type=snapshot.type,
            label=snapshot.label,
            geometry=snapshot.geometry,
            _validated_token=_VALIDATED_FACTORY_TOKEN,
        )

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "troncon": self.troncon,
            "type": self.type,
            "label": self.label,
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Railway:
        railway_id = payload.get("id")
        railway_code = payload.get("code")
        railway_troncon = payload.get("troncon")
        railway_type = payload.get("type")
        railway_label = payload.get("label")
        if not isinstance(railway_id, str):
            raise ValueError("Railway payload id must be a string")
        if not isinstance(railway_code, str):
            raise ValueError("Railway payload code must be a string")
        if not isinstance(railway_troncon, int):
            raise ValueError("Railway payload troncon must be an integer")
        if not isinstance(railway_type, str):
            raise ValueError("Railway payload type must be a string")
        if not isinstance(railway_label, str):
            raise ValueError("Railway payload label must be a string")
        return cls.validate(
            id=railway_id,
            code=railway_code,
            troncon=railway_troncon,
            type=railway_type,
        )

    def __repr__(self) -> str:
        return f"{self._label} - {self._code} - {self._troncon}"
