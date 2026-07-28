from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Final, Literal

import geopandas
import pandas as pd
import pandera.geopandas as pg
import pandera.pandas as pa
from loguru import logger
from pandas.errors import DatabaseError

from core.geo.dataset_schemas import (
    GaresDeVoyageursSchema,
    LignesParTypeSchema,
    ReferentielPkGpsSchema,
    normalize_dataset_code_ligne,
)
from core.geo.exceptions import (
    DatasetCorruptionError,
    DatasetError,
    DatasetNotFoundError,
    SchemaValidationError,
)

_SQLITE_BIND_SCALAR_TYPES = (str, int, float, bytes, type(None))


def _count_sql_placeholders(sql: str) -> int:
    """Count ``?`` bind placeholders in a SQL statement."""
    return sql.count("?")


def _validate_query_parameters(parameters: dict[str, object]) -> tuple[object, ...]:
    """Validate and normalize bind parameters for SQLite prepared statements."""
    bound_parameters: list[object] = []
    for name, value in parameters.items():
        if isinstance(value, bool):
            raise TypeError(
                f"Query parameter {name!r} must not be a bool; use int instead"
            )
        if not isinstance(value, _SQLITE_BIND_SCALAR_TYPES):
            raise TypeError(
                f"Query parameter {name!r} must be str, int, float, bytes, or None"
            )
        bound_parameters.append(value)
    return tuple(bound_parameters)


def _preprocess_gares_de_voyageurs(
    df: geopandas.GeoDataFrame,
) -> geopandas.GeoDataFrame:
    """Preprocess the gares de voyageurs dataset."""
    without_position = df.drop(columns="position_geographique")
    typed = without_position.astype({"segment_drg": "category"})
    return typed.set_index("codes_uic", drop=False).sort_index()


def _preprocess_lignes_par_type(df: geopandas.GeoDataFrame) -> geopandas.GeoDataFrame:
    """Preprocess the lignes par type dataset."""
    typed = df.astype({"type_ligne": "category"})
    cleaned = typed.drop(
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
    cleaned = cleaned.assign(
        code_ligne=cleaned["code_ligne"].map(normalize_dataset_code_ligne),
        rg_troncon=cleaned["rg_troncon"].astype(int),
    )
    return cleaned.set_index(["code_ligne", "rg_troncon"], drop=False).sort_index()


def _preprocess_referentiel_pk_gps(df: pd.DataFrame) -> geopandas.GeoDataFrame:
    """Preprocess the referentiel pk gps dataset.
    This dataset is a SQLite database with a single table called ``kilometric_points``.
    Most of the preprocessing is done at the database level.
    """
    normalized = df.copy()
    normalized.columns = normalized.columns.map(lambda c: c.lower())
    typed = normalized.astype({"ligne": "category", "label": "string"})

    typed["geometry"] = geopandas.GeoSeries.from_xy(
        typed["longitude"], typed["latitude"], crs="EPSG:4326"
    )
    without_lat_lon = typed.drop(columns=["latitude", "longitude"])

    # Ensure geometry is present before map use.
    cleaned = without_lat_lon.dropna(subset=["geometry"])
    dataframe = cleaned.assign(
        code_ligne=cleaned["code_ligne"].astype(int),
        rg_troncon=cleaned["rg_troncon"].astype(int),
        km=cleaned["km"].astype(int),
    )

    geodataframe = geopandas.GeoDataFrame(
        dataframe, geometry="geometry", crs="EPSG:4326"
    )
    return geodataframe.set_index(
        ["code_ligne", "rg_troncon", "km"], drop=False
    ).sort_index()


@dataclass(frozen=True)
class DatasetDefinition:

    id: str
    name: str
    lg: str
    format: Literal["csv", "json", "geojson", "shapefile", "parquet", "sqlite"]
    # Text encoding for the file (GeoJSON, CSV, etc.);
    encoding: str | None
    last_update: str | None
    hash: str  # sha256sum
    schema: pa.DataFrameSchema | pg.GeoDataFrameSchema
    preprocessing: (
        Callable[
            [geopandas.GeoDataFrame | pd.DataFrame],
            geopandas.GeoDataFrame | pd.DataFrame,
        ]
        | None
    ) = None

    @property
    def full_path(self) -> Path:

        return (
            Path(__file__)
            .resolve()
            .parent.joinpath("statics", ".".join([self.name, self.format]))
        )


class DatasetRepository:

    BASE_URL = Path(__file__).resolve().parent.joinpath("statics")

    DATASET_DEFINITIONS: Final[Dict[str, DatasetDefinition]] = {
        "gares-de-voyageurs": DatasetDefinition(
            id="gares-de-voyageurs",
            name="gares-de-voyageurs",
            lg="fr",
            format="geojson",
            encoding="utf-8",
            last_update=None,
            hash="65cea4575dda5b43f42626d1377f6e340fe173f3d7db3cafd879099686b12588",
            schema=GaresDeVoyageursSchema,
            preprocessing=_preprocess_gares_de_voyageurs,
        ),
        "lignes-par-type": DatasetDefinition(
            id="lignes-par-type",
            name="lignes-par-type",
            lg="fr",
            format="geojson",
            encoding="utf-8",
            last_update=None,
            hash="931b0f0917b8be71c0f97d6bb90d4c34c9d9ff9d4a389b01a4de9a58c9c62066",
            schema=LignesParTypeSchema,
            preprocessing=_preprocess_lignes_par_type,
        ),
        "referentiel_pk_gps": DatasetDefinition(
            id="referentiel_pk_gps",
            name="pk",
            lg="fr",
            format="sqlite",
            encoding=None,
            last_update=None,
            hash="a6e4db7351a6f2d7e9b315538176719e5e1f0b2cf9ae7cd148f99322bd39c3c7",
            schema=ReferentielPkGpsSchema,
            preprocessing=_preprocess_referentiel_pk_gps,
        ),
    }

    @classmethod
    def get_all_dataset_definitions(cls) -> list[DatasetDefinition]:

        return list(cls.DATASET_DEFINITIONS.values())

    @classmethod
    def get_dataset_definition(cls, id: str) -> DatasetDefinition | None:

        return cls.DATASET_DEFINITIONS.get(id, None)


class DatasetManager:
    """Manager for datasets."""

    REPOSITORY: Final[DatasetRepository] = DatasetRepository()

    @classmethod
    def _get_required_definition(cls, dataset_id: str) -> DatasetDefinition:
        """Return a dataset definition or raise when the id is unknown."""
        definition = cls.REPOSITORY.get_dataset_definition(dataset_id)
        if definition is None:
            raise DatasetNotFoundError(
                dataset_id,
                f"Dataset {dataset_id!r} not found",
            )
        return definition

    @classmethod
    def _ensure_dataset_file(cls, definition: DatasetDefinition) -> Path:
        """Verify the packaged asset path exists and is a regular file."""
        path = definition.full_path
        if not path.exists():
            logger.error(
                "Dataset asset missing",
                dataset_id=definition.id,
                path=str(path),
                format=definition.format,
            )
            raise DatasetNotFoundError(
                definition.id,
                f"Dataset asset not found: {path}",
                path=path,
            )
        if not path.is_file():
            logger.error(
                "Dataset asset is not a file",
                dataset_id=definition.id,
                path=str(path),
                format=definition.format,
            )
            raise DatasetNotFoundError(
                definition.id,
                f"Dataset asset is not a file: {path}",
                path=path,
            )
        return path

    @classmethod
    def _verify_dataset_hash(cls, definition: DatasetDefinition) -> None:
        """Verify the on-disk asset matches the catalog SHA-256 hash."""
        path = cls._ensure_dataset_file(definition)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_hash = digest.hexdigest()
        if actual_hash != definition.hash:
            logger.error(
                "Dataset asset hash mismatch",
                dataset_id=definition.id,
                path=str(path),
                format=definition.format,
                expected_hash=definition.hash,
                actual_hash=actual_hash,
            )
            raise DatasetCorruptionError(
                definition.id,
                f"Dataset asset hash mismatch for {definition.id!r}: {path}",
                path=path,
                expected_hash=definition.hash,
                actual_hash=actual_hash,
            )

    @classmethod
    def _preflight_dataset_asset(cls, definition: DatasetDefinition) -> None:
        """Ensure the dataset asset exists and matches its catalog hash."""
        cls._verify_dataset_hash(definition)

    @classmethod
    def _wrap_dataset_read_error(
        cls,
        definition: DatasetDefinition,
        error: Exception,
        *,
        operation: str,
    ) -> None:
        """Re-raise dataset-layer errors and wrap unexpected read failures."""
        if isinstance(error, DatasetError):
            raise error
        path = definition.full_path
        logger.error(
            "Dataset asset read failed",
            dataset_id=definition.id,
            path=str(path),
            format=definition.format,
            operation=operation,
            error=str(error),
            exc_info=True,
        )
        raise DatasetCorruptionError(
            definition.id,
            f"Failed to read dataset {definition.id!r} ({operation}): {path}",
            path=path,
        ) from error

    @classmethod
    def read(
        cls, id: str, encoding: str | None = None
    ) -> geopandas.GeoDataFrame | pd.DataFrame:
        """Read a dataset from the repository.

        Args:
            id: The dataset id.
            encoding: Text encoding; defaults to :attr:`DatasetDefinition.encoding` for the id
                (``utf-8`` for shipped GeoJSON, ``latin-1`` for the referentiel PK CSV). Pass
                a value to override the definition.

        Returns:
            The dataset as a geopandas.GeoDataFrame or pd.DataFrame.

        Raises:
            DatasetNotFoundError: Unknown dataset id or missing asset file.
            DatasetCorruptionError: Hash mismatch or unreadable/corrupted asset.
            SchemaValidationError: Schema validation failed after a successful read.
        """
        definition = cls._get_required_definition(id)
        cls._preflight_dataset_asset(definition)

        effective_encoding = encoding if encoding is not None else definition.encoding
        if effective_encoding is None:
            effective_encoding = "utf-8"

        try:
            if definition.format in ["geojson", "shapefile"]:
                gdf: geopandas.GeoDataFrame = geopandas.read_file(
                    definition.full_path, encoding=effective_encoding
                )
                validated_gdf = cls._validate(definition, gdf)
                return cls._preprocess(definition, validated_gdf)

            if definition.format == "csv":
                df: pd.DataFrame = pd.read_csv(
                    definition.full_path,
                    sep=";",
                    header=0,
                    encoding=effective_encoding,
                )
                validated_df = cls._validate(definition, df)
                return cls._preprocess(definition, validated_df)

            if definition.format == "json":
                raise NotImplementedError

            if definition.format == "parquet":
                raise NotImplementedError

            if definition.format == "sqlite":
                with sqlite3.connect(definition.full_path) as conn:
                    sqlite_df = pd.read_sql(
                        sql="SELECT * FROM kilometric_points", con=conn
                    )
                validated_df = cls._validate(definition, sqlite_df)
                return cls._preprocess(definition, validated_df)

            raise DatasetCorruptionError(
                definition.id,
                f"Unsupported dataset format {definition.format!r} for {definition.id!r}",
                path=definition.full_path,
            )
        except NotImplementedError:
            raise
        except Exception as error:
            cls._wrap_dataset_read_error(
                definition,
                error,
                operation=f"read:{definition.format}",
            )
            raise AssertionError("unreachable")

    @classmethod
    def query(
        cls, id: str, sql: str, **parameters: object
    ) -> pd.DataFrame | geopandas.GeoDataFrame:
        """Query a dataset using a parameterized SQL statement.

        Args:
            id: The dataset id.
            sql: The SQL query to execute. Use ``?`` placeholders for bind values.
            **parameters: Bind values passed in keyword order to the prepared statement.

        Returns:
            The result of the SQL query as a pandas DataFrame or geopandas.GeoDataFrame.

        Raises:
            DatasetNotFoundError: Unknown dataset id or missing asset file.
            DatasetCorruptionError: Hash mismatch or unreadable SQLite asset.
            ValueError: Dataset is not SQLite or bind parameter contract is invalid.
            SchemaValidationError: Schema validation failed on non-empty query results.
        """
        definition = cls._get_required_definition(id)
        if definition.format != "sqlite":
            raise ValueError(f"Dataset {id} is not a SQLite database")

        bound_parameters = _validate_query_parameters(parameters)
        placeholder_count = _count_sql_placeholders(sql)
        if placeholder_count != len(bound_parameters):
            parameter_names = list(parameters.keys())
            raise ValueError(
                "SQL placeholder count does not match parameter count: "
                f"{placeholder_count} placeholders, {len(bound_parameters)} parameters "
                f"({parameter_names})"
            )

        try:
            cls._preflight_dataset_asset(definition)
            with sqlite3.connect(definition.full_path) as conn:
                query_result = pd.read_sql(
                    sql=sql,
                    con=conn,
                    params=bound_parameters,
                )
        except sqlite3.OperationalError as error:
            logger.error(
                "SQLite dataset query failed",
                dataset_id=definition.id,
                path=str(definition.full_path),
                sql=sql,
                parameter_names=list(parameters.keys()),
                error=error,
            )
            raise
        except DatabaseError as error:
            logger.error(
                "SQLite dataset query failed",
                dataset_id=definition.id,
                path=str(definition.full_path),
                sql=sql,
                parameter_names=list(parameters.keys()),
                error=error,
            )
            raise
        except Exception as error:
            cls._wrap_dataset_read_error(
                definition,
                error,
                operation="query:sqlite-connect",
            )
            raise AssertionError("unreachable")

        if not query_result.empty:
            validated_df = cls._validate(definition, query_result)
            return cls._preprocess(definition, validated_df)
        return query_result

    @classmethod
    def _validate(
        cls, definition: DatasetDefinition, data: geopandas.GeoDataFrame | pd.DataFrame
    ) -> geopandas.GeoDataFrame | pd.DataFrame:
        """Validate the data against the schema.

        Args:
            definition: The dataset definition.
            data: The data to validate.

        Returns:
            The validated data.
        """

        try:
            validated_data: geopandas.GeoDataFrame | pd.DataFrame = (
                definition.schema.validate(check_obj=data, lazy=True)
            )
            return validated_data
        except pa.errors.SchemaErrors as e:
            logger.error(
                "Dataset validation failed",
                definition=definition,
                errors=e,
            )
            raise SchemaValidationError from e

    @classmethod
    def _preprocess(
        cls, definition: DatasetDefinition, data: geopandas.GeoDataFrame | pd.DataFrame
    ) -> geopandas.GeoDataFrame | pd.DataFrame:
        """Preprocess the data."""
        if definition.preprocessing:
            return definition.preprocessing(data)
        return data
