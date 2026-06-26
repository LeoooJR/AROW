"""Location domain types and referentiel marker validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, cast

import pandas as pd

from core.geo.datasets import DatasetManager

# Maximum WGS84 delta (degrees) between clicked map coords and referentiel row.
_COORD_TOLERANCE_DEGREES: float = 0.0001


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

    def is_default(self) -> bool:
        """Return True if the location is the default location."""
        return self.lat == 0.0 and self.lon == 0.0 and self.label is None

    def to_payload(self) -> dict[str, float | str | None]:
        """Convert the location to a payload."""
        return {
            "lat": self.lat,
            "lon": self.lon,
            "label": self.label,
        }

    @staticmethod
    def from_payload(payload: dict[str, object]) -> Location:
        """Create a location from a payload."""
        label = payload.get("label")
        return Location(
            lat=float(cast(float | int | str, payload["lat"])),
            lon=float(cast(float | int | str, payload["lon"])),
            label=None if label is None else str(label),
        )


@dataclass(frozen=True, slots=True)
class ValidatedMarkerLocation:
    """Canonical milestone location resolved from the referentiel dataset."""

    marker_id: str
    lat: float
    lon: float
    label: str | None
    line: str | None = None
    type_reper: str | None = None


@lru_cache(maxsize=1)
def _referentiel_pk_dataset() -> pd.DataFrame:
    """Load and normalize the PK referentiel once per process."""
    dataset: pd.DataFrame = DatasetManager.read("referentiel_pk_gps")
    dataset = dataset.copy()
    dataset.columns = dataset.columns.map(lambda column: str(column).lower())
    return dataset


def validate_marker_location(
    marker_id: str,
    line: str,
    latitude: float,
    longitude: float,
) -> ValidatedMarkerLocation:
    """Resolve and validate a map milestone against ``referentiel_pk_gps``.

    Args:
        marker_id: PK string from map feature properties (e.g. ``001+000``).
        line: Line string from map feature properties (e.g. ``001``).
        latitude: Latitude reported by the map click handler.
        longitude: Longitude reported by the map click handler.

    Returns:
        Canonical milestone coordinates and metadata from the referentiel.

    Raises:
        ValueError: When the marker is unknown or click coords diverge from referentiel.
    """
    normalized_marker_id = str(marker_id).strip()
    if not normalized_marker_id:
        raise ValueError("Marker id must not be empty")

    referentiel = _referentiel_pk_dataset()
    pk_series = referentiel["pk"].astype("string").str.strip()
    matches = referentiel.loc[pk_series == normalized_marker_id]
    if matches.empty:
        raise ValueError(f"Unknown milestone marker id: {normalized_marker_id!r}")

    if len(matches.index) > 1:
        # If there are multiple matches, filter by line.
        normalized_line = str(line).strip()
        line_series = matches["ligne"].astype("string").str.strip()
        matches_for_line = matches.loc[line_series == normalized_line]
        if matches_for_line.empty:
            raise ValueError(f"Unknown milestone line: {line!r}")
        if len(matches_for_line.index) > 1:
            raise ValueError(f"Multiple matches for line: {line!r}")
        matches = matches_for_line

    row = matches.iloc[0]  # Convert to Series for consistent indexing.
    dataset_lat = float(row["latitude"])
    dataset_lon = float(row["longitude"])

    lat_delta = abs(dataset_lat - latitude)
    lon_delta = abs(dataset_lon - longitude)
    if lat_delta > _COORD_TOLERANCE_DEGREES or lon_delta > _COORD_TOLERANCE_DEGREES:
        raise ValueError(
            "Clicked coordinates do not match referentiel for marker "
            f"{normalized_marker_id!r}: clicked=({latitude}, {longitude}), "
            f"referentiel=({dataset_lat}, {dataset_lon})"
        )

    line_value = row.get("ligne")
    type_reper_value = row.get("type_reper")
    dataset_line = None if pd.isna(line_value) else str(line_value)
    type_reper = None if pd.isna(type_reper_value) else str(type_reper_value)
    label = (
        f"{normalized_marker_id} / {dataset_line}"
        if dataset_line
        else normalized_marker_id
    )

    return ValidatedMarkerLocation(
        marker_id=normalized_marker_id,
        lat=dataset_lat,
        lon=dataset_lon,
        label=label,
        line=dataset_line,
        type_reper=type_reper,
    )


def clear_referentiel_pk_cache() -> None:
    """Clear the cached referentiel dataset (for tests)."""
    _referentiel_pk_dataset.cache_clear()
