"""Tests for DatasetManager SQL query support and asset robustness."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import geopandas
import pandas as pd
import pytest
from pandas.errors import DatabaseError

from core.geo.datasets import DatasetDefinition, DatasetManager, DatasetRepository
from core.geo.exceptions import DatasetCorruptionError, DatasetNotFoundError

_REFERENTIEL_QUERY = """
SELECT * FROM kilometric_points
WHERE code_ligne = ?
AND rg_troncon = ?
AND km = ?
"""


def test_query_referentiel_returns_preprocessed_geodataframe_with_geometry() -> None:
    result = DatasetManager.query(
        id="referentiel_pk_gps",
        sql=_REFERENTIEL_QUERY,
        code_ligne=1000,
        rg_troncon=1,
        km=1,
    )

    assert isinstance(result, geopandas.GeoDataFrame)
    assert len(result) == 1
    assert "geometry" in result.columns
    assert result.iloc[0]["label"] == "001+000"
    assert result.iloc[0]["geometry"].geom_type == "Point"


def test_query_referentiel_empty_result_returns_empty_dataframe() -> None:
    result = DatasetManager.query(
        id="referentiel_pk_gps",
        sql=_REFERENTIEL_QUERY,
        code_ligne=1000,
        rg_troncon=1,
        km=999999,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_query_referentiel_treats_injection_like_value_as_literal() -> None:
    result = DatasetManager.query(
        id="referentiel_pk_gps",
        sql=_REFERENTIEL_QUERY,
        code_ligne="001000' OR 1=1 --",
        rg_troncon=1,
        km=1,
    )

    assert result.empty


def test_query_rejects_unsupported_parameter_type() -> None:
    with pytest.raises(TypeError, match="must be str, int, float, bytes, or None"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql=_REFERENTIEL_QUERY,
            code_ligne={"value": 1000},
            rg_troncon=1,
            km=1,
        )


def test_query_rejects_bool_parameter() -> None:
    with pytest.raises(TypeError, match="must not be a bool"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql=_REFERENTIEL_QUERY,
            code_ligne=True,
            rg_troncon=1,
            km=1,
        )


def test_query_rejects_placeholder_parameter_count_mismatch() -> None:
    with pytest.raises(ValueError, match="placeholder count does not match"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql="SELECT * FROM kilometric_points WHERE code_ligne = ?",
            code_ligne=1000,
            rg_troncon=1,
            km=1,
        )


def test_query_referentiel_invalid_sql_raises_database_error() -> None:
    with pytest.raises(DatabaseError, match="missing_table"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql="SELECT * FROM missing_table",
        )


def test_query_unknown_dataset_raises_not_found() -> None:
    with pytest.raises(DatasetNotFoundError, match="Dataset 'missing' not found"):
        DatasetManager.query(id="missing", sql="SELECT 1")


def test_read_unknown_dataset_raises_not_found() -> None:
    with pytest.raises(DatasetNotFoundError, match="Dataset 'missing' not found"):
        DatasetManager.read("missing")


def test_read_missing_asset_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = DatasetRepository.get_dataset_definition("gares-de-voyageurs")
    assert definition is not None
    missing_definition = replace(definition, name="arow-missing-asset")

    monkeypatch.setattr(
        DatasetManager.REPOSITORY,
        "get_dataset_definition",
        lambda dataset_id: (
            missing_definition if dataset_id == "gares-de-voyageurs" else None
        ),
    )

    with pytest.raises(
        DatasetNotFoundError, match="Dataset asset not found"
    ) as exc_info:
        DatasetManager.read("gares-de-voyageurs")

    error = exc_info.value
    assert error.dataset_id == "gares-de-voyageurs"
    assert error.path == missing_definition.full_path


def test_read_non_file_asset_raises_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = DatasetRepository.get_dataset_definition("gares-de-voyageurs")
    assert definition is not None
    directory_path = tmp_path / "gares-de-voyageurs.geojson"
    directory_path.mkdir()

    fake_definition = MagicMock(spec=DatasetDefinition)
    fake_definition.id = definition.id
    fake_definition.format = definition.format
    fake_definition.encoding = definition.encoding
    fake_definition.hash = definition.hash
    fake_definition.schema = definition.schema
    fake_definition.preprocessing = definition.preprocessing
    fake_definition.full_path = directory_path

    monkeypatch.setattr(
        DatasetManager.REPOSITORY,
        "get_dataset_definition",
        lambda dataset_id: (
            fake_definition if dataset_id == "gares-de-voyageurs" else None
        ),
    )

    with pytest.raises(
        DatasetNotFoundError, match="Dataset asset is not a file"
    ) as exc_info:
        DatasetManager.read("gares-de-voyageurs")

    assert exc_info.value.path == directory_path


def test_read_hash_mismatch_raises_corruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = DatasetRepository.get_dataset_definition("gares-de-voyageurs")
    assert definition is not None
    tampered_definition = replace(definition, hash="0" * 64)

    monkeypatch.setattr(
        DatasetManager.REPOSITORY,
        "get_dataset_definition",
        lambda dataset_id: (
            tampered_definition if dataset_id == "gares-de-voyageurs" else None
        ),
    )

    with pytest.raises(DatasetCorruptionError, match="hash mismatch") as exc_info:
        DatasetManager.read("gares-de-voyageurs")

    error = exc_info.value
    assert error.dataset_id == "gares-de-voyageurs"
    assert error.expected_hash == "0" * 64
    assert error.actual_hash is not None
    assert error.actual_hash != error.expected_hash


def test_read_corrupted_geojson_raises_corruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _broken_read_file(*_args: object, **_kwargs: object) -> geopandas.GeoDataFrame:
        raise ValueError("invalid geojson payload")

    monkeypatch.setattr(geopandas, "read_file", _broken_read_file)
    monkeypatch.setattr(
        DatasetManager, "_preflight_dataset_asset", lambda _definition: None
    )

    with pytest.raises(DatasetCorruptionError, match="Failed to read dataset"):
        DatasetManager.read("gares-de-voyageurs")


def test_query_hash_mismatch_raises_corruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = DatasetRepository.get_dataset_definition("referentiel_pk_gps")
    assert definition is not None
    tampered_definition = replace(definition, hash="0" * 64)

    monkeypatch.setattr(
        DatasetManager.REPOSITORY,
        "get_dataset_definition",
        lambda dataset_id: (
            tampered_definition if dataset_id == "referentiel_pk_gps" else None
        ),
    )

    with pytest.raises(DatasetCorruptionError, match="hash mismatch"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql=_REFERENTIEL_QUERY,
            code_ligne=1000,
            rg_troncon=1,
            km=1,
        )


def test_query_missing_asset_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = DatasetRepository.get_dataset_definition("referentiel_pk_gps")
    assert definition is not None
    missing_definition = replace(definition, name="arow-missing-sqlite")

    monkeypatch.setattr(
        DatasetManager.REPOSITORY,
        "get_dataset_definition",
        lambda dataset_id: (
            missing_definition if dataset_id == "referentiel_pk_gps" else None
        ),
    )

    with pytest.raises(DatasetNotFoundError, match="Dataset asset not found"):
        DatasetManager.query(
            id="referentiel_pk_gps",
            sql=_REFERENTIEL_QUERY,
            code_ligne=1000,
            rg_troncon=1,
            km=1,
        )


def test_gares_de_voyageurs_index_is_codes_uic_with_retained_columns() -> None:
    dataset = DatasetManager.read("gares-de-voyageurs")

    assert dataset.index.name == "codes_uic"
    assert dataset.index.is_unique
    assert "codes_uic" in dataset.columns
    assert "nom" in dataset.columns
    assert "geometry" in dataset.columns


def test_lignes_par_type_index_is_code_ligne_and_rg_troncon() -> None:
    dataset = DatasetManager.read("lignes-par-type")

    assert list(dataset.index.names) == ["code_ligne", "rg_troncon"]
    assert dataset.index.is_unique
    assert "code_ligne" in dataset.columns
    assert "rg_troncon" in dataset.columns
    assert "idgaia" in dataset.columns
    assert "geometry" in dataset.columns


def test_referentiel_pk_gps_index_is_code_ligne_rg_troncon_km() -> None:
    dataset = DatasetManager.read("referentiel_pk_gps")

    assert list(dataset.index.names) == ["code_ligne", "rg_troncon", "km"]
    assert dataset.index.is_unique
    assert "code_ligne" in dataset.columns
    assert "rg_troncon" in dataset.columns
    assert "km" in dataset.columns
    assert "label" in dataset.columns
    assert "geometry" in dataset.columns
