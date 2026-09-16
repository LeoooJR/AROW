"""Pandera schema definitions for packaged geo datasets."""

from __future__ import annotations

from typing import Optional

import geopandas
import numpy as np
import pandas as pd
import pandera.geopandas as pg
import pandera.pandas as pa
from pandera.typing import INT64, Float, Int, Int32, Object, Series, String
from pandera.typing.geopandas import GeoSeries


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


def _gares_geometry_is_point_or_empty(geom_series: geopandas.GeoSeries) -> pd.Series:
    """Stations: null geometry (missing) or a Point in WGS84 (file order: lon, lat on Point)."""
    return geom_series.isna() | (geom_series.geom_type == "Point")


def _lignes_geometry_is_line_or_multiline(
    geom_series: geopandas.GeoSeries,
) -> pd.Series:
    """Ligne tronçons: LineString or MultiLineString."""
    return geom_series.geom_type.isin(["LineString", "MultiLineString"])


class GaresDeVoyageursSchema(pg.GeoDataFrameModel):
    """Schema for the packaged passenger-station GeoJSON dataset."""

    nom: Series[String] = pg.Field(
        nullable=False, unique=True, description="The official name of the station"
    )
    libellecourt: Series[String] = pg.Field(
        nullable=False,
        unique=True,
        str_length=3,
        description="The short name of the station",
    )
    # one or more A/B/C tokens joined by semicolons (e.g. "A;B", "A:A", "A;B;A").
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
    def _check_gares_point_geometry(cls, series: geopandas.GeoSeries) -> bool:
        """Stations: missing geometry (NA) or Point features."""
        return bool((_gares_geometry_is_point_or_empty(series)).all())


def normalize_dataset_code_ligne(value: object) -> str:
    """Normalize numeric line codes to six digits for indexed lookups."""
    normalized = str(value).strip()
    if normalized.isdigit():
        return normalized.zfill(6)
    return normalized


class LignesParTypeSchema(pg.GeoDataFrameModel):
    """Schema for the packaged railway-line segment GeoJSON dataset."""

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
    def _check_lignes_line_or_multiline(cls, series: geopandas.GeoSeries) -> bool:
        return bool(_lignes_geometry_is_line_or_multiline(series).all())


class ReferentielPkGpsSchema(pa.DataFrameModel):
    """PK / hectometric referential with WGS84 columns (``referentiel_pk_gps`` CSV)."""

    ligne: Series[String] = pa.Field(
        nullable=False, description="Line id (e.g. 001000-1)."
    )
    code_ligne: Series[Int] = pa.Field(nullable=False, description="Numeric line code.")
    km: Series[Int] = pa.Field(nullable=False, description="Kilometer.")
    label: Series[String] = pa.Field(
        nullable=False, description="Point kilométrique (e.g. 000+052)."
    )
    # Some rows have no tronçon; full-file reads use nullable integer.
    rg_troncon: Series[INT64] = pa.Field(
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
