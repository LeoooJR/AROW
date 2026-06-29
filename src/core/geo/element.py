from __future__ import annotations

from abc import ABC
from functools import lru_cache

import pandas as pd

from core.geo.datasets import DatasetManager
from core.geo.exceptions import MilestoneValidationError
from core.geo.location import Location

# Maximum WGS84 delta (degrees) between clicked map coords and referentiel row.
_COORD_TOLERANCE_DEGREES: float = 0.0001


@lru_cache(maxsize=1)
def _referentiel_pk_dataset() -> pd.DataFrame:
    """Load and normalize the PK referentiel once per process."""
    dataset: pd.DataFrame = DatasetManager.read("referentiel_pk_gps")
    dataset = dataset.copy()
    dataset.columns = dataset.columns.map(lambda column: str(column).lower())
    return dataset


def clear_referentiel_pk_cache() -> None:
    """Clear the cached referentiel dataset (for tests)."""
    _referentiel_pk_dataset.cache_clear()


class MapElement(ABC):
    """
    Abstract base class for all map elements.
    """

    def __init__(self, id: str, location: Location):
        self._id = id
        self._location = location

    @property
    def id(self) -> str:
        """
        Return the id of the map element.
        """
        return self._id

    @property
    def location(self) -> Location:
        """
        Return the location of the map element.
        """
        return self._location


class Station(MapElement):
    """
    A station on the map.
    """

    def __init__(self, id: str, location: Location):
        super().__init__(id, location)


class Milestone(MapElement):
    """
    A milestone on the map.
    """

    def __init__(self, id: str, line: str, type: str, label: str, location: Location):
        super().__init__(id, location)
        self._line = line
        self._type = type
        self._label = label

    @property
    def line(self) -> str:
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

    @classmethod
    def validate(cls, id: str, line: str, location: Location) -> Milestone:
        """Resolve and validate a map milestone against ``referentiel_pk_gps``.

        Args:
            id: PK string from map feature properties (e.g. ``001+000``).
            line: Line string from map feature properties (e.g. ``001``).
            location: Location reported by the map click handler.

        Returns:
            Validated milestone.

        Raises:
            MilestoneValidationError: When the milestone is unknown or location diverges from referentiel.
        """
        normalized_id = str(id).strip()
        if not normalized_id:
            raise MilestoneValidationError("Milestone id must not be empty")

        referentiel = _referentiel_pk_dataset()
        milestone_series: pd.Series = referentiel["pk"].astype("string").str.strip()
        matches: pd.DataFrame = referentiel.loc[milestone_series == normalized_id]
        if matches.empty:
            raise MilestoneValidationError(f"Unknown milestone id: {normalized_id!r}")

        if len(matches.index) > 1:
            # If there are multiple matches, filter by line.
            normalized_line = str(line).strip()
            line_series: pd.Series = matches["ligne"].astype("string").str.strip()
            matches_for_line: pd.DataFrame = matches.loc[line_series == normalized_line]
            if matches_for_line.empty:
                raise MilestoneValidationError(f"Unknown milestone line: {line!r}")
            if len(matches_for_line.index) > 1:
                raise MilestoneValidationError(f"Multiple matches for line: {line!r}")
            # Update in broader scope to avoid re-fetching the dataset.
            matches = matches_for_line

        row = matches.iloc[0]  # Convert to Series for consistent indexing.
        referentiel_lat = float(row["latitude"])
        referentiel_lon = float(row["longitude"])

        lat_delta = abs(referentiel_lat - location.lat)
        lon_delta = abs(referentiel_lon - location.lon)
        if lat_delta > _COORD_TOLERANCE_DEGREES or lon_delta > _COORD_TOLERANCE_DEGREES:
            raise MilestoneValidationError(
                "Clicked coordinates do not match referentiel for marker "
                f"{normalized_id!r}: clicked=({location.lat}, {location.lon}), "
                f"referentiel=({referentiel_lat}, {referentiel_lon})"
            )

        line_value = row.get("ligne")
        type_reper_value = row.get("type_reper")
        referentiel_line = None if pd.isna(line_value) else str(line_value)
        referentiel_type = None if pd.isna(type_reper_value) else str(type_reper_value)
        label = (
            f"{normalized_id} / {referentiel_line}"
            if referentiel_line
            else normalized_id
        )

        return cls(
            id=normalized_id,
            line=referentiel_line or "",
            type=referentiel_type or "",
            label=label,
            location=Location(
                lat=referentiel_lat,
                lon=referentiel_lon,
                label=None,
            ),
        )


class Railway(MapElement):
    """
    A railway on the map.
    """

    def __init__(self, id: str, location: Location):
        super().__init__(id, location)
