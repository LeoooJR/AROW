"""Tests for railway validation in core.geo.element."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from shapely.geometry import MultiLineString

from core.geo.datasets import DatasetManager
from core.geo.element import Railway, clear_lignes_par_type_cache
from core.geo.exceptions import RailwayValidationError


@pytest.fixture(autouse=True)
def _clear_lignes_cache() -> Iterator[None]:
    clear_lignes_par_type_cache()
    yield
    clear_lignes_par_type_cache()


def test_railway_validate_by_code_returns_merged_multilinestring() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    sample = referentiel.iloc[0]
    code = str(sample["code_ligne"]).strip()

    validated = Railway.validate(code=code)

    assert validated.code == code
    assert validated.id == str(sample["idgaia"]).strip()
    assert validated.label == str(sample["lib_ligne"])
    assert isinstance(validated.geometry, MultiLineString)


def test_railway_validate_by_id_merges_segmented_geometry() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    segment_counts = referentiel.groupby("idgaia").size()
    multi_id = str(segment_counts[segment_counts > 1].index[0]).strip()
    expected_segments = int(segment_counts[multi_id])

    validated = Railway.validate(id=multi_id)

    assert validated.id == multi_id
    assert isinstance(validated.geometry, MultiLineString)
    assert len(validated.geometry.geoms) == expected_segments


def test_railway_validate_prefers_idgaia_lookup_when_both_keys_provided() -> None:
    referentiel = DatasetManager.read("lignes-par-type")
    sample = referentiel.iloc[0]
    idgaia = str(sample["idgaia"]).strip()
    wrong_code = "999999"

    validated = Railway.validate(id=idgaia, code=wrong_code)

    assert validated.id == idgaia
    assert validated.code == str(sample["code_ligne"]).strip()


def test_railway_validate_rejects_unknown_code() -> None:
    with pytest.raises(RailwayValidationError, match="Unknown railway code_ligne"):
        Railway.validate(code="999999")
