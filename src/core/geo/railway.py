"""Railway line domain model and referentiel validation."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal, cast

import geopandas
import pandas as pd
from shapely.geometry import LineString, MultiLineString

from core.geo.base import (
    _VALIDATED_FACTORY_TOKEN,
    MapElement,
    is_validated_construction,
)
from core.geo.datasets import DatasetManager
from core.geo.exceptions import RailwayValidationError
from core.geo.geometry import deserialize_geometry
from core.payload import Payload


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


def normalize_code_ligne(value: object) -> str:
    """Normalize numeric line codes to six digits for referentiel matching."""
    normalized = str(value).strip()
    if normalized.isdigit():
        return normalized.zfill(6)
    return normalized


def clear_lignes_par_type_cache() -> None:
    """Clear the cached lignes-par-type dataset (for tests)."""
    _lignes_par_type_dataset.cache_clear()


class Railway(MapElement, Payload):
    """A railway on the map."""

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

        Do not use this constructor directly; use ``Railway.validate()`` instead.
        """
        if not isinstance(geometry, (LineString, MultiLineString)):
            raise TypeError("Geometry must be a LineString or MultiLineString")
        super().__init__(id, geometry)
        self._code = code
        self._troncon = troncon
        self._type = type
        self._label = label
        self._is_validated = is_validated_construction(_validated_token)

    @property
    def is_validated(self) -> bool:
        """Return True when the railway was created by ``Railway.validate``."""
        return self._is_validated

    @property
    def code(self) -> str:
        """Return the code of the railway."""
        return self._code

    @property
    def troncon(self) -> int:
        """Return the troncon of the railway."""
        return self._troncon

    @property
    def type(self) -> str:
        """Return the type of the railway."""
        return self._type

    @property
    def label(self) -> str:
        """Return the label of the railway."""
        return self._label

    @staticmethod
    def is_idgaia(id: str) -> bool:
        """Return True if the id is a valid SNCF Gaïa line identifier."""
        return (
            re.match(
                r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                id,
            )
            is not None
        )

    @staticmethod
    def is_code_ligne(code: str) -> bool:
        """Return True if the code is a valid numeric line code."""
        return re.match(r"^\d{6}$", code) is not None

    @staticmethod
    def resolve_line_identifier_type(
        identifier: str,
    ) -> Literal["idgaia", "code_ligne"]:
        """Resolve the line identifier type from the given identifier."""
        if Railway.is_idgaia(identifier):
            return "idgaia"
        if Railway.is_code_ligne(identifier):
            return "code_ligne"
        raise ValueError(f"Invalid line identifier: {identifier!r}")

    @classmethod
    def validate(
        cls,
        id: str | None = None,
        code: str | None = None,
        troncon: int | None = None,
    ) -> Railway:
        """Resolve and validate a map railway against ``lignes-par-type``."""
        lookup_key_name: str | None = None
        normalized_lookup_key: str | None = None
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

        referentiel = _lignes_par_type_dataset()
        try:
            if lookup_key_name == "code_ligne":
                row = referentiel.loc[
                    (normalize_code_ligne(normalized_lookup_key), normalized_troncon)
                ]
            else:
                matches = referentiel.loc[
                    (referentiel["idgaia"] == normalized_lookup_key)
                    & (referentiel["rg_troncon"] == normalized_troncon)
                ]
                if matches.empty:
                    raise KeyError(normalized_lookup_key)
                row = matches.iloc[0]
        except KeyError as error:
            raise RailwayValidationError(
                f"Unknown railway {lookup_key_name}: {normalized_lookup_key!r}"
            ) from error

        if isinstance(row, pd.DataFrame):
            raise RailwayValidationError(
                f"Multiple matches for railway {lookup_key_name}: {normalized_lookup_key!r}"
            )

        id_key = _normalize_lookup_key(row["idgaia"])
        code_key = _normalize_lookup_key(row["code_ligne"])
        if id_key is None or code_key is None:
            raise ValueError("Missing railway lookup key in lignes-par-type row")

        return Railway(
            id=id_key,
            code=code_key,
            troncon=int(row["rg_troncon"]),
            type=row["type_ligne"],
            label=row["lib_ligne"],
            geometry=row["geometry"],
            _validated_token=_VALIDATED_FACTORY_TOKEN,
        )

    @classmethod
    def from_validated_summary(
        cls,
        *,
        id: str,
        code: str,
        troncon: int,
        type: str,
        label: str,
        geometry_wkb_b64: str,
    ) -> Railway:
        """Rebuild a validated railway on the main thread without referentiel lookup."""
        geometry = deserialize_geometry(geometry_wkb_b64)
        if not isinstance(geometry, (LineString, MultiLineString)):
            raise ValueError("Railway geometry must be a LineString or MultiLineString")
        return cls(
            id=id,
            code=code,
            troncon=troncon,
            type=type,
            label=label,
            geometry=geometry,
            _validated_token=_VALIDATED_FACTORY_TOKEN,
        )

    def serialize(self, **kwargs) -> dict[str, object]:
        """Serialize the validated railway lookup key.

        Args:
            **kwargs: Reserved serialization options.

        Returns:
            Railway identifier, line code, and segment number.
        """
        return {
            "id": self.id,
            "code": self.code,
            "troncon": self.troncon,
        }

    @classmethod
    def deserialize(cls, payload: dict[str, object], **kwargs) -> Railway:
        """Deserialize and validate a railway lookup key.

        Args:
            payload: Serialized railway fields.
            **kwargs: Reserved deserialization options.

        Returns:
            Railway resolved from the referential dataset.

        Raises:
            ValueError: If a required field has an invalid type or value.
        """
        railway_id = payload.get("id")
        if not isinstance(railway_id, str):
            raise ValueError("Railway payload id must be a string")
        railway_code = payload.get("code")
        if not isinstance(railway_code, str):
            raise ValueError("Railway payload code must be a string")
        railway_troncon = payload.get("troncon")
        if not isinstance(railway_troncon, int):
            raise ValueError("Railway payload troncon must be an integer")
        return cls.validate(id=railway_id, code=railway_code, troncon=railway_troncon)

    def __repr__(self) -> str:
        return f"{self._label} - {self._code} - {self._troncon}"
