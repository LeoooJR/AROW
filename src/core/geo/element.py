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
    type: str
    label: str
    geometry: MultiLineString


@lru_cache(maxsize=1)
def _referentiel_pk_dataset() -> pd.DataFrame:
    """Load and normalize the PK referentiel once per process."""
    dataset: pd.DataFrame = DatasetManager.read("referentiel_pk_gps")
    dataset = dataset.copy()
    dataset.columns = dataset.columns.map(lambda column: str(column).lower())
    return dataset


@lru_cache(maxsize=1)
def _lignes_par_type_dataset() -> geopandas.GeoDataFrame:
    """Load and normalize the lignes-par-type dataset once per process."""
    dataset: geopandas.GeoDataFrame = DatasetManager.read("lignes-par-type")
    dataset = dataset.copy()
    dataset = dataset.astype({"type_ligne": "category"})
    dataset = dataset.drop(
        columns=[
            "x_d_l93",
            "y_d_l93",
            "x_f_l93",
            "y_f_l93",
            "x_d_wgs84",
            "y_d_wgs84",
            "x_f_wgs84",
            "y_f_wgs84",
            "c_geo_d",
            "c_geo_f",
            "geo_point_2d",
        ]
    )
    return dataset


def _normalize_lookup_key(value: object) -> str | None:
    """Return a stripped string lookup key, or None when the value is missing."""
    if pd.isna(value):
        return None
    normalized = str(value).strip()
    return normalized or None


def _scalar_field_value(group: geopandas.GeoDataFrame, column: str) -> str:
    """Read the first non-null scalar in a segment group as a string field."""
    series = group[column]
    unique_values = series.dropna().unique()
    if len(unique_values) == 0:
        return ""
    return str(unique_values[0])


def _segment_linestrings(group: geopandas.GeoDataFrame) -> list[LineString]:
    """Expand referentiel segment geometries into individual line strings."""
    linestrings: list[LineString] = []
    for geometry in group.geometry:
        if isinstance(geometry, LineString):
            linestrings.append(geometry)
        elif isinstance(geometry, MultiLineString):
            linestrings.extend(geometry.geoms)
        else:
            raise RailwayValidationError(
                f"Unsupported railway geometry type: {type(geometry).__name__}"
            )
    if not linestrings:
        raise RailwayValidationError(
            "Railway geometry must contain at least one segment"
        )
    return linestrings


def _railway_snapshot_from_segments(
    group: geopandas.GeoDataFrame,
) -> _ValidatedRailwaySnapshot:
    """Merge segmented referentiel rows into one multi-linestring railway snapshot."""
    segment_geometries = _segment_linestrings(group)
    return _ValidatedRailwaySnapshot(
        id=_scalar_field_value(group, "idgaia"),
        code=_scalar_field_value(group, "code_ligne"),
        type=_scalar_field_value(group, "type_ligne"),
        label=_scalar_field_value(group, "lib_ligne"),
        geometry=MultiLineString(segment_geometries),
    )


@lru_cache(maxsize=1)
def _railway_lookup_indexes() -> (
    tuple[dict[str, _ValidatedRailwaySnapshot], dict[str, _ValidatedRailwaySnapshot]]
):
    """Build O(1) railway lookup indexes keyed by SNCF Gaïa id and numeric line code."""
    referentiel = _lignes_par_type_dataset()
    by_idgaia: dict[str, _ValidatedRailwaySnapshot] = {}
    by_code_ligne: dict[str, _ValidatedRailwaySnapshot] = {}

    idgaia_keys = referentiel["idgaia"].map(_normalize_lookup_key)
    for lookup_key, group in referentiel.groupby(idgaia_keys, sort=False):
        if lookup_key is None:
            continue
        by_idgaia[lookup_key] = _railway_snapshot_from_segments(group)

    code_keys = referentiel["code_ligne"].map(_normalize_lookup_key)
    for lookup_key, group in referentiel.groupby(code_keys, sort=False):
        if lookup_key is None:
            continue
        by_code_ligne[lookup_key] = _railway_snapshot_from_segments(group)

    return by_idgaia, by_code_ligne


def _normalize_code_ligne(value: object) -> str:
    """Normalize numeric line codes to six digits for referentiel matching."""
    normalized = str(value).strip()
    if normalized.isdigit():
        return normalized.zfill(6)
    return normalized


def clear_referentiel_pk_cache() -> None:
    """Clear the cached referentiel dataset (for tests)."""
    _referentiel_pk_dataset.cache_clear()


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
        id: str,
        line: Railway,
        type: str,
        geometry: Point,
        label: str | None = None,
    ):
        """
        Initialize a milestone with the given id, line, type, label and geometry.

        Args:
            id: The id of the milestone.
            line: The line of the milestone. Must be a Railway.
            type: The type of the milestone.
            label: The label of the milestone.
            geometry: The geometry of the milestone. Must be a Point.

        Raises:
            TypeError: If the geometry is not a Point.
            RailwayValidationError: If the line is not a valid railway.
        """
        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")
        super().__init__(
            id,
            geometry,
        )
        if not isinstance(line, Railway):
            raise TypeError("Line must be a Railway")
        validated_line = Railway.validate(id=line.id)
        if not self._is_on_line(validated_line):
            raise MilestoneValidationError(f"Milestone {id} is not on line {line}")
        self._line = validated_line
        self._type = type
        self._label = label or f"{super().id} on {validated_line}"

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
    def validate(cls, id: str, line: str | Railway, geometry: Point) -> Milestone:
        """Resolve and validate a map milestone against ``referentiel_pk_gps``.

        Args:
            id: PK string from map feature properties (e.g. ``001+000``).
            line: Line string or Railway from map feature properties (e.g. ``590000``).
            geometry: The geometry of the milestone. Must be a Point.

        Returns:
            Validated milestone.

        Raises:
            MilestoneValidationError: When the milestone is unknown or location diverges from referentiel.
        """
        normalized_id = str(id).strip()
        if not normalized_id:
            raise MilestoneValidationError("Milestone id must not be empty")

        if not isinstance(geometry, Point):
            raise TypeError("Geometry must be a Point")

        if not isinstance(line, str) and not isinstance(line, Railway):
            raise TypeError("Line must be a string or a Railway")

        if isinstance(line, str):
            line_identifier_type = Railway.resolve_line_identifier_type(line)
            line_lookup_key = line
        else:  # Railway instance
            line_identifier_type = "idgaia"  # Most precise and reliable source.
            line_lookup_key = (
                line.id
            )  # Extract SNCF Gaïa line identifier from Railway instance, do not trust other properties.

        if line_identifier_type == "idgaia":
            validated_line = Railway.validate(id=line_lookup_key)
        elif line_identifier_type == "code_ligne":
            validated_line = Railway.validate(code=line_lookup_key)
        else:
            raise MilestoneValidationError(f"Invalid line identifier: {line!r}")

        referentiel = _referentiel_pk_dataset()
        milestone_series: pd.Series = referentiel["pk"].astype("string").str.strip()
        matches: pd.DataFrame = referentiel.loc[milestone_series == normalized_id]
        if matches.empty:
            raise MilestoneValidationError(f"Unknown milestone id: {normalized_id!r}")

        if len(matches.index) > 1:
            # If there are multiple matches, filter by line.
            code_ligne_series: pd.Series = matches["code_ligne"].map(
                _normalize_code_ligne
            )
            normalized_railway_code = _normalize_code_ligne(validated_line.code)
            matches_for_line: pd.DataFrame = matches.loc[
                code_ligne_series == normalized_railway_code
            ]
            if matches_for_line.empty:
                raise MilestoneValidationError(
                    f"Unknown milestone {normalized_id!r} on line with code_ligne: {validated_line.code!r}"
                )
            if len(matches_for_line.index) > 1:
                raise MilestoneValidationError(
                    f"Multiple matches for {normalized_id!r} on line with code_ligne: {validated_line.code!r}"
                )
            # Update in broader scope to avoid re-fetching the dataset.
            matches = matches_for_line

        row: pd.Series = matches.iloc[0]  # Convert to Series for consistent indexing.
        referentiel_lat = float(row["latitude"])
        referentiel_lon = float(row["longitude"])
        referentiel_geometry = Point(referentiel_lon, referentiel_lat)

        if referentiel_geometry.distance(geometry) > _COORD_TOLERANCE_DEGREES:
            raise MilestoneValidationError(
                "Geometry does not match referentiel for milestone "
                f"{normalized_id!r}: geometry={geometry}, referentiel={referentiel_geometry}"
            )

        type_reper_value = row.get("type_reper")
        referentiel_type = None if pd.isna(type_reper_value) else str(type_reper_value)
        label = f"{normalized_id} on {validated_line}"

        return cls(
            id=normalized_id,
            line=validated_line,
            type=referentiel_type or "",
            label=label,
            geometry=referentiel_geometry,
        )

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "id": self.id,
            "line": self.line.serialize(**kwargs),
            "type": self.type,
            "label": self.label,
            "geometry": _serialize_geometry(self.geometry, **kwargs),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Milestone:
        line = payload.get("line")
        if not isinstance(line, dict):
            raise ValueError("Line must be a dictionary")
        line = Railway.deserialize(line, **kwargs)
        milestone_id = payload.get("id")
        milestone_type = payload.get("type")
        milestone_label = payload.get("label")
        if not isinstance(milestone_id, str):
            raise ValueError("Milestone payload id must be a string")
        if not isinstance(milestone_type, str):
            raise ValueError("Milestone payload type must be a string")
        if milestone_label is not None and not isinstance(milestone_label, str):
            raise ValueError("Milestone payload label must be a string or null")
        return cls(
            id=milestone_id,
            line=line,
            type=milestone_type,
            label=milestone_label,
            geometry=_deserialize_geometry(payload.get("geometry")),
        )

    def __repr__(self) -> str:
        return self._label


class Railway(MapElement, Payload):
    """
    A railway on the map.
    """

    def __init__(
        self,
        id: str,
        code: str,
        type: str,
        label: str,
        geometry: LineString | MultiLineString,
    ):
        """
        Initialize a railway with the given id, code, type and geometry.

        Args:
            id: The id of the railway.
            code: The code of the railway.
            type: The type of the railway.
            label: The label of the railway.
            geometry: The geometry of the railway. LineString or merged MultiLineString.
        """
        if not isinstance(geometry, (LineString, MultiLineString)):
            raise TypeError("Geometry must be a LineString or MultiLineString")
        super().__init__(id, geometry)
        self._code = code
        self._type = type
        self._label = label

    @property
    def code(self) -> str:
        """
        Return the code of the railway.
        """
        return self._code

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
        type: str | None = None,
    ) -> Railway:
        """Resolve and validate a map railway against ``lignes-par-type``. At least one of the id or code must be provided.

        Args:
            id: SNCF Gaïa line identifier (UUID). Must be provided if numeric line code is not provided or unknown.
            code: Numeric line code (6 digits). Must be provided if SNCF Gaïa line identifier is not provided or unknown.
            location: Location reported by the map click handler.
            type: Line category (e.g. principale, raccordement).

        Returns:
            Validated railway.

        Raises:
            RailwayValidationError: When the railway is unknown or location diverges from referentiel.
        """
        lookup_key_name = None
        normalized_lookup_key = None
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

        if type is not None:
            normalized_type = str(type).strip()
            if not normalized_type:
                raise RailwayValidationError("Railway type must not be empty")

        if lookup_key_name is None or normalized_lookup_key is None:
            raise RailwayValidationError(
                "At least one of the id or code must be provided"
            )

        by_idgaia, by_code_ligne = _railway_lookup_indexes()
        if lookup_key_name == "idgaia":
            snapshot = by_idgaia.get(normalized_lookup_key)
        else:
            snapshot = by_code_ligne.get(normalized_lookup_key)
        if snapshot is None:
            raise RailwayValidationError(
                f"Unknown railway {lookup_key_name}: {normalized_lookup_key!r}"
            )

        return cls(
            id=snapshot.id,
            code=snapshot.code,
            type=snapshot.type,
            label=snapshot.label,
            geometry=snapshot.geometry,
        )

    def serialize(self, **kwargs) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "type": self.type,
            "label": self.label,
            "geometry": _serialize_geometry(self.geometry, **kwargs),
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Railway:
        railway_id = payload.get("id")
        railway_code = payload.get("code")
        railway_type = payload.get("type")
        railway_label = payload.get("label")
        if not isinstance(railway_id, str):
            raise ValueError("Railway payload id must be a string")
        if not isinstance(railway_code, str):
            raise ValueError("Railway payload code must be a string")
        if not isinstance(railway_type, str):
            raise ValueError("Railway payload type must be a string")
        if not isinstance(railway_label, str):
            raise ValueError("Railway payload label must be a string")
        return cls(
            id=railway_id,
            code=railway_code,
            type=railway_type,
            label=railway_label,
            geometry=_deserialize_geometry(payload.get("geometry", None)),
        )

    def __repr__(self) -> str:
        return self._label
