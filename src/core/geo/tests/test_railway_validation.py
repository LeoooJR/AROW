"""Tests for railway validation in core.geo.element."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from shapely.geometry import LineString

from core.geo.datasets import DatasetManager
from core.geo.element import Railway, clear_lignes_par_type_cache
from core.geo.exceptions import RailwayValidationError


@pytest.fixture(autouse=True)
def _clear_lignes_cache() -> Iterator[None]:
    clear_lignes_par_type_cache()
    yield
    clear_lignes_par_type_cache()


def test_railway_validate_by_code_returns_segment_linestring() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    sample = referentiel.iloc[0]
    code = str(sample["code_ligne"]).strip()
    troncon = int(sample["rg_troncon"])

    validated = Railway.validate(code=code, troncon=troncon)

    assert validated.is_validated
    assert validated.code == code
    assert validated.troncon == troncon
    assert validated.id == str(sample["idgaia"]).strip()
    assert validated.label == str(sample["lib_ligne"])
    assert isinstance(validated.geometry, LineString)


def test_railway_validate_by_id_returns_segment_linestring() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    sample = referentiel.iloc[0]
    idgaia = str(sample["idgaia"]).strip()
    troncon = int(sample["rg_troncon"])

    validated = Railway.validate(id=idgaia, troncon=troncon)

    assert validated.id == idgaia
    assert validated.troncon == troncon
    assert isinstance(validated.geometry, LineString)


def test_railway_validate_prefers_idgaia_lookup_when_both_keys_provided() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    sample = referentiel.iloc[0]
    idgaia = str(sample["idgaia"]).strip()
    troncon = int(sample["rg_troncon"])
    wrong_code = "999999"

    validated = Railway.validate(id=idgaia, code=wrong_code, troncon=troncon)

    assert validated.id == idgaia
    assert validated.code == str(sample["code_ligne"]).strip()


def test_railway_validate_rejects_unknown_code() -> None:
    with pytest.raises(RailwayValidationError, match="Unknown railway code_ligne"):
        Railway.validate(code="999999", troncon=1)


def test_railway_validate_requires_troncon() -> None:
    with pytest.raises(
        RailwayValidationError, match="Railway troncon must be provided"
    ):
        Railway.validate(code="001000")
