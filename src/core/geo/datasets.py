from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Final, Literal, Optional

import geopandas
import numpy as np
import pandas as pd
import pandera.geopandas as pg
import pandera.pandas as pa
from geo.exceptions import SchemaValidationError
from loguru import logger
from pandera.typing import INT64, Float, Int, Int32, Object, Series, String
from pandera.typing.geopandas import GeoSeries

# --- Vectorized checks for object columns that hold nested GeoJSON dicts (lon/lat) ---


def _is_lon_lat_dict(value: object) -> bool:
    """True if *value* is a dict with numeric ``lon`` and ``lat`` (GeoJSON-style point)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if not isinstance(value, dict):
        return False
    if "lon" not in value or "lat" not in value:
        return False
    lon, lat = value["lon"], value["lat"]
    if isinstance(lon, (bool, np.bool_)) or isinstance(lat, (bool, np.bool_)):
        return False
    return isinstance(lon, (int, float, np.floating, np.integer)) and isinstance(
        lat, (int, float, np.floating, np.integer)
    )


def _series_lon_lat_dicts_ok(series: pd.Series) -> pd.Series:
    """Element-wise: every cell is a dict with numeric lon/lat (lignes export has no nulls in these)."""
    return series.map(_is_lon_lat_dict)


# --- Ligne / gares geometry: non-empty rows must be allow-listed types ---


def _gares_geometry_is_point_or_empty(geom_series: "geopandas.GeoSeries") -> pd.Series:
    """Stations: null geometry (missing) or a Point in WGS84 (file order: lon, lat on Point)."""
    return geom_series.isna() | (geom_series.geom_type == "Point")


def _lignes_geometry_is_line_or_multiline(
    geom_series: "geopandas.GeoSeries",
) -> pd.Series:
    """Ligne tronçons: LineString or MultiLineString."""
    return geom_series.geom_type.isin(["LineString", "MultiLineString"])


# --- Referentiel: French CSV sometimes uses comma decimals; full reads may infer string columns. ---


def _parse_referentiel_wgs84_and_rg_troncon(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce ``latitude`` / ``longitude`` to float (comma or dot decimals) and ``RG_TRONCON`` to nullable int.

    The static file mixes inferable float columns for small head reads and all-string coordinates for
    long reads; this parser makes :class:`ReferentielPkGpsSchema` checks consistent.
    """
    if df.empty:
        return df
    out = df.copy()
    for col in ("latitude", "longitude"):
        if col not in out.columns:
            continue
        ser = out[col]
        if pd.api.types.is_numeric_dtype(ser):
            out[col] = pd.to_numeric(ser, errors="coerce")
        else:
            out[col] = pd.to_numeric(
                ser.astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace(" ", "", regex=False)
                .str.strip(),
                errors="coerce",
            )
    if "RG_TRONCON" in out.columns:
        rt = out["RG_TRONCON"]
        if not isinstance(
            rt.dtype, pd.Int64Dtype
        ) and not pd.api.types.is_integer_dtype(rt):
            out["RG_TRONCON"] = (
                pd.to_numeric(rt, errors="coerce").round().astype("Int64")
            )
    return out


class GaresDeVoyageursSchema(pg.GeoDataFrameModel):

    nom: Series[String] = pg.Field(
        nullable=False, unique=True, description="The official name of the station"
    )
    libellecourt: Series[String] = pg.Field(
        nullable=False,
        unique=True,
        str_length=3,
        description="The short name of the station",
    )
    # one or more A/B/C tokens joined by semicolons (e.g. "A;B", "A;A", "A;B;A").
    segment_drg: Series[String] = pg.Field(
        nullable=False,
        str_matches=r"^(?:A|B|C)(?:;[ABC])*$",
        description="The DRG segment of the station (A/B/C tokens, semicolon-separated for composite)",
    )
    # Present in the GeoJSON; often all-null; may be filled with structured metadata in some exports.
    position_geographique: Series[Object] = pg.Field(
        nullable=True,
        description="Optional extra geographic metadata from the source (usually null).",
    )
    codeinsee: Series[String] = pg.Field(
        nullable=False,
        unique=False,
        str_matches=r"^\d{5}$",
        description="The INSEE code of the station (5 digits).",
    )
    codes_uic: Series[String] = pg.Field(
        nullable=False,
        unique=True,
        str_matches=r"^\d{8}(?:;\d{8})*$",
        description="The UIC code(s) of the station, 8 digits; multiple codes separated by ';'.",
    )
    geometry: GeoSeries = pg.Field(
        nullable=True,
        description="The geometry of the station in the WGS84 coordinate system (Point, or null).",
    )

    @pg.check("geometry", ignore_na=False)
    @classmethod
    def _check_gares_point_geometry(cls, series: "geopandas.GeoSeries") -> bool:
        """Stations: missing geometry (NA) or Point features."""
        return bool((_gares_geometry_is_point_or_empty(series)).all())


class LignesParTypeSchema(pg.GeoDataFrameModel):

    type_ligne: Series[String] = pg.Field(
        nullable=False, description="Line category (e.g. principale, raccordement)."
    )
    idgaia: Series[String] = pg.Field(
        nullable=False,
        str_matches=r"(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        description="SNCF Gaïa line identifier (UUID).",
    )
    code_ligne: Series[String] = pg.Field(
        nullable=False,
        str_length=6,
        str_matches=r"^\d{6}$",
        description="Numeric line code (6 digits in the static export).",
    )
    lib_ligne: Series[String] = pg.Field(
        nullable=False, description="Line label / name."
    )
    # GeoPandas may infer int32 for small integers.
    rg_troncon: Series[Int32] = pg.Field(
        nullable=False,
        description="Rang du tronçon (integer segment index).",
    )
    # PK strings use '+' or '-' as km/hectometric separator; some edge rows use a leading letter (D+841).
    pkd: Series[String] = pg.Field(
        nullable=False,
        str_matches=r"^[\dA-Z]+[+\-][\dA-Z+]+$",
        description="PK début (SNCF kilometric point, + or - separator).",
    )
    pkf: Series[String] = pg.Field(
        nullable=False,
        str_matches=r"^[\dA-Z]+[+\-][\dA-Z+]+$",
        description="PK fin (SNCF kilometric point, + or - separator).",
    )
    x_d_l93: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Début X Lambert 93 (m)."
    )
    y_d_l93: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Début Y Lambert 93 (m)."
    )
    x_f_l93: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Fin X Lambert 93 (m)."
    )
    y_f_l93: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Fin Y Lambert 93 (m)."
    )
    x_d_wgs84: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Début longitude WGS84 (deg)."
    )
    y_d_wgs84: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Début latitude WGS84 (deg)."
    )
    x_f_wgs84: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Fin longitude WGS84 (deg)."
    )
    y_f_wgs84: Optional[Series[Float]] = pg.Field(
        nullable=False, description="Fin latitude WGS84 (deg)."
    )
    c_geo_d: Optional[Series[String]] = pg.Field(
        nullable=False,
        description="Coordinates as comma-separated string (lat,lon order in source).",
    )
    c_geo_f: Optional[Series[Object]] = pg.Field(
        nullable=False,
        description="Fin point as {lon, lat} dict (GeoJSON-style).",
    )
    geo_point_2d: Optional[Series[Object]] = pg.Field(
        nullable=False,
        description="Representative point of the line as {lon, lat} dict.",
    )
    geometry: GeoSeries = pg.Field(
        nullable=False,
        description="Line geometry in WGS84 (LineString or MultiLineString).",
    )

    @pg.check("c_geo_f")
    @classmethod
    def _check_c_geo_f_lon_lat_dicts(cls, series: pd.Series) -> bool:
        return bool(_series_lon_lat_dicts_ok(series).all())

    @pg.check("geo_point_2d")
    @classmethod
    def _check_geo_point_2d_lon_lat_dicts(cls, series: pd.Series) -> bool:
        return bool(_series_lon_lat_dicts_ok(series).all())

    @pg.check("geometry")
    @classmethod
    def _check_lignes_line_or_multiline(cls, series: "geopandas.GeoSeries") -> bool:
        return bool(_lignes_geometry_is_line_or_multiline(series).all())


class ReferentielPkGpsSchema(pa.DataFrameModel):
    """PK / hectometric referential with WGS84 columns (``referentiel_pk_gps`` CSV)."""

    @pa.dataframe_parser
    @classmethod
    def _parse_referentiel_numerics(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Parse comma-formatted WGS84 strings and tronçon index before validation.

        The CSV is sometimes inferred as all-string coordinates on full read; the referentiel file
        also uses comma as decimal separator in some BaseJSN rows. This keeps ``latitude``/``longitude``
        in float form for WGS84 checks.
        """
        return _parse_referentiel_wgs84_and_rg_troncon(df)

    TYPE_REPER: Series[String] = pa.Field(
        nullable=False, description="Type de repère (T, Hectomètre, etc.)."
    )
    PK: Series[String] = pa.Field(
        nullable=False, description="Point kilométrique (e.g. 000+052)."
    )
    LIGNE: Series[String] = pa.Field(
        nullable=False, description="Line id (e.g. 001000-1)."
    )
    CODE_LIGNE: Series[Int] = pa.Field(nullable=False, description="Numeric line code.")
    # Some rows have no tronçon; full-file reads use nullable integer.
    RG_TRONCON: Series[INT64] = pa.Field(
        nullable=True,
        description="Rang du tronçon (nullable when absent in source).",
    )
    latitude: Series[Float] = pa.Field(
        nullable=False,
        in_range=(-90.0, 90.0),
        description="Latitude WGS84 (deg).",
    )
    longitude: Series[Float] = pa.Field(
        nullable=False,
        in_range=(-180.0, 180.0),
        description="Longitude WGS84 (deg).",
    )


@dataclass(frozen=True)
class DatasetDefinition:

    id: Final[str]
    name: Final[str]
    lg: Final[str]
    format: Final[Literal["csv", "json", "geojson", "shapefile", "parquet"]]
    # Text encoding for the file (GeoJSON, CSV, etc.); fiona / pandas use this for strings.
    encoding: Final[str]
    last_update: Final[str]
    hash: Final[str]  # sha256sum
    schema: Final[pa.DataFrameSchema | pg.GeoDataFrameSchema]

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
            hash="5bbc36c7be9b44499dacf9ffdde200085d4ba731d8561ce8cd2665df0ee1e31d",
            schema=GaresDeVoyageursSchema,
        ),
        "lignes-par-type": DatasetDefinition(
            id="lignes-par-type",
            name="lignes-par-type",
            lg="fr",
            format="geojson",
            encoding="utf-8",
            last_update=None,
            hash="2a0da177f597f1fa6122e18d510b3a601b9315bf2c2ab511e58adee2b054b18c",
            schema=LignesParTypeSchema,
        ),
        "referentiel_pk_gps": DatasetDefinition(
            id="referentiel_pk_gps",
            name="referentiel_pk_gps",
            lg="fr",
            format="csv",
            encoding="latin-1",
            last_update=None,
            hash="0b106045e866aee214ea86700b50d6f6ab4c783a267a76c41d6674cde2de6d95",
            schema=ReferentielPkGpsSchema,
        ),
    }

    @classmethod
    def get_all_dataset_definitions(cls) -> list[DatasetDefinition]:

        return list(cls.DATASET_DEFINITIONS.values())

    @classmethod
    def get_dataset_definition(cls, id: str) -> DatasetDefinition | None:

        return cls.DATASET_DEFINITIONS.get(id, None)


class DatasetManager:

    REPOSITORY: DatasetRepository = DatasetRepository()

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
        """

        definition: DatasetDefinition | None = cls.REPOSITORY.get_dataset_definition(id)

        if definition:

            effective_encoding: str = (
                definition.encoding if encoding is None else encoding
            )

            if definition.format in ["geojson", "shapefile"]:

                gdf: geopandas.GeoDataFrame = geopandas.read_file(
                    definition.full_path, encoding=effective_encoding
                )
                return cls._validate(definition, gdf)

            else:

                if definition.format == "csv":

                    df: pd.DataFrame = pd.read_csv(
                        definition.full_path,
                        sep=";",
                        header=0,
                        encoding=effective_encoding,
                    )

                    return cls._validate(definition, df)

                elif definition.format == "json":

                    raise NotImplementedError

                elif definition.format == "parquet":

                    raise NotImplementedError

        raise ValueError(f"Dataset {id} not found")

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
                f"Validation errors for dataset",
                definition=definition,
                errors=e,
            )
            raise SchemaValidationError
