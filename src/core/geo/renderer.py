from pathlib import Path
from typing import Dict, Final, Literal, Tuple

import folium
import geopandas
import pandas as pd
import xyzservices.providers as xyz
from folium.plugins import Fullscreen, MarkerCluster, MousePosition, Search
from folium.utilities import JsCode
from loguru import logger

from core.geo.bridge import (
    WEB_CHANNEL_INIT_JS,
    WEB_CHANNEL_SCRIPT_SRC,
    on_marker_clicked_js_code,
)
from core.geo.datasets import DatasetManager
from core.geo.icons import Icons

# Columns embedded in Folium GeoJSON for milestone layers (tooltip/popup only).
_MILESTONE_GEOJSON_COLUMNS: Final[Tuple[str, ...]] = (
    "pk",
    "ligne",
    "code_ligne",
    "type_reper",
    "geometry",
)


class MapRenderer:

    DEFAULT_LATITUDE: Final[float] = 46.232193

    DEFAULT_LONGITUDE: Final[float] = 2.209667

    CRS_FRANCE: Final[str] = "EPSG:2154"

    ZOOM_START: Final[int] = 6

    def __init__(self):

        # Canvas renderer reduces DOM load for many CircleMarkers (milestones).
        self.map = folium.Map(
            tiles="OpenStreetMap",
            location=(self.DEFAULT_LATITUDE, self.DEFAULT_LONGITUDE),
            zoom_start=self.ZOOM_START,
            prefer_canvas=True,
        )

        self._load_datasets()

        self._create_layers()

    def _load_datasets(self):

        manager: DatasetManager = DatasetManager()

        stations_geodataset: geopandas.GeoDataFrame = manager.read("gares-de-voyageurs")

        # Drop columns that are not needed for the map
        stations_geodataset: geopandas.GeoDataFrame = stations_geodataset.drop(
            columns="position_geographique"
        )

        # Convert columns to categorical types for better performance
        self.stations_geodataset: geopandas.GeoDataFrame = stations_geodataset.astype(
            {"segment_drg": "category"}
        )

        railways_geodataset: geopandas.GeoDataFrame = manager.read(id="lignes-par-type")

        # Convert columns to categorical types for better performance
        railways_geodataset: geopandas.GeoDataFrame = railways_geodataset.astype(
            {"type_ligne": "category"}
        )

        # Drop columns that are not needed for the map
        self.railways_geodataset: geopandas.GeoDataFrame = railways_geodataset.drop(
            columns=[
                "idgaia",
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

        milestones_dataset: pd.DataFrame = manager.read("referentiel_pk_gps")

        # Convert columns names to lowercarse for consistency
        milestones_dataset.columns = milestones_dataset.columns.map(lambda c: c.lower())

        # Convert columns to categorical types for better performance
        milestones_dataset: pd.DataFrame = milestones_dataset.astype(
            {"type_reper": "category", "ligne": "category", "code_ligne": "category"}
        )
        # Vectorized WGS84: comma decimals in source CSV.
        lon: pd.Series = pd.to_numeric(
            milestones_dataset["longitude"]
            .astype("string")
            .str.replace(",", ".", regex=False),
            errors="coerce",
        )
        lat: pd.Series = pd.to_numeric(
            milestones_dataset["latitude"]
            .astype("string")
            .str.replace(",", ".", regex=False),
            errors="coerce",
        )
        milestones_dataset["geometry"]: geopandas.GeoSeries = (
            geopandas.GeoSeries.from_xy(lon, lat, crs="EPSG:4326")
        )
        milestones_dataset = milestones_dataset.drop(columns=["latitude", "longitude"])

        # PK string (e.g. "001+000" -> 1.0 km, "012+500" -> 12.5 km), vectorized.
        _pk: pd.Series = milestones_dataset["pk"].astype("string")
        _parts = _pk.str.strip().str.split("+", n=1, expand=True)
        _km_part: pd.Series = pd.to_numeric(_parts[0], errors="coerce")
        _m_part: pd.Series = pd.to_numeric(_parts[1], errors="coerce")
        milestones_dataset["kilometers"]: pd.Series = _km_part + _m_part / 1000.0

        # Ensure that the geometry, code_ligne, and kilometers columns are not null, even if must not happen.
        milestones_dataset: pd.DataFrame = milestones_dataset.dropna(
            subset=["geometry", "code_ligne", "kilometers"]
        )
        self.milestones_geodataset: geopandas.GeoDataFrame = geopandas.GeoDataFrame(
            milestones_dataset, crs="EPSG:4326"
        )
        # Drop the intermediate frame to lower peak RAM once geometry lives in GeoDataFrame.
        del milestones_dataset

        milestones_kilometer_geodataset: geopandas.GeoDataFrame = (
            self.milestones_geodataset[
                self.milestones_geodataset["type_reper"] == "Kilomètre"
            ]
        )

        self._milestones_visibility_settings: Final[
            Dict[str, Dict[str, int | float]]
        ] = {
            "LOW": {"threshold": 10, "spacing": 10.0, "tolerance": 0.5},
            "MEDIUM": {"threshold": 14, "spacing": 1.0, "tolerance": 0.05},
        }

        def _at_distance_mask(
            kilometers: pd.Series, settings: Literal["LOW", "MEDIUM"]
        ) -> pd.Series:
            """Check if the distance between two milestones is within the tolerance for the given settings.

            Args:
                kilometers: The kilometers of the milestones.
                settings: The settings for the milestones.

            Returns:
                A boolean series indicating if the distance between two milestones is within the tolerance for the given settings.
            """
            spacing: float = self._milestones_visibility_settings[settings]["spacing"]
            tolerance: float = self._milestones_visibility_settings[settings][
                "tolerance"
            ]
            remainder: pd.Series = kilometers % spacing
            return (remainder <= tolerance) | ((spacing - remainder) <= tolerance)

        # Low-zoom markers: rule LOW, without per-row Python loops.
        low_mask: pd.Series = _at_distance_mask(
            milestones_kilometer_geodataset["kilometers"], settings="LOW"
        )
        subset_indices: list[int] = milestones_kilometer_geodataset.index[
            low_mask
        ].tolist()

        self._milestones_low_zoom_geodataset: geopandas.GeoDataFrame = (
            milestones_kilometer_geodataset.loc[sorted(subset_indices)]
        )
        self._milestones_medium_zoom_geodataset: geopandas.GeoDataFrame = (
            milestones_kilometer_geodataset.loc[
                ~milestones_kilometer_geodataset.index.isin(subset_indices)
            ]
        )
        self._milestone_high_zoom_geodataset: geopandas.GeoDataFrame = (
            self.milestones_geodataset[
                self.milestones_geodataset["type_reper"] != "Kilomètre"
            ]
        )

        # Slim GeoJSON payloads for Folium (only columns used by tooltip/popup).
        self._milestones_low_zoom_for_map: geopandas.GeoDataFrame = (
            self._milestones_low_zoom_geodataset.loc[
                :, list(_MILESTONE_GEOJSON_COLUMNS)
            ].copy()
        )
        self._milestones_medium_zoom_for_map: geopandas.GeoDataFrame = (
            self._milestones_medium_zoom_geodataset.loc[
                :, list(_MILESTONE_GEOJSON_COLUMNS)
            ].copy()
        )

        _n_km: int = len(milestones_kilometer_geodataset)
        _n_low: int = len(self._milestones_low_zoom_geodataset)
        _n_med: int = len(self._milestones_medium_zoom_geodataset)
        _n_hi: int = len(self._milestone_high_zoom_geodataset)
        logger.info(
            "Milestone layers built: kilometer_only={} low_zoom={} medium_zoom={} "
            "high_zoom_non_km={}",
            _n_km,
            _n_low,
            _n_med,
            _n_hi,
            kilometer_only_rows=_n_km,
            low_zoom_rows=_n_low,
            medium_zoom_rows=_n_med,
            high_zoom_non_km_rows=_n_hi,
        )
        logger.opt(lazy=True).debug(
            "Milestone slim GeoJSON serialized length (chars, for HTML weight): "
            "low={low_len} medium={med_len}",
            low_len=lambda: len(self._milestones_low_zoom_for_map.to_json()),
            med_len=lambda: len(self._milestones_medium_zoom_for_map.to_json()),
        )

    def _create_layers(self):

        DEFAULT_LIGNE_COLOR = "#94a3b8"  # unknown – light slate
        SEARCH_LIGNE_COLOR = "#f97316"

        TYPE_LIGNE_COLOR = {
            "Ligne proprement dite": "#1e3a5f",  # main line – dark blue
            "Raccordement": "#64748b",  # siding/connection – slate
            "Voie-mère d'embranchement": "#059669",  # branch – emerald
            "Voie de desserte de voies ferrées de port": "#b45309",  # port access – amber
        }

        STATION_ON_EACH_FEATURE = JsCode("""
        function(f, l) {
            var p = f.properties || {};
            var nom = p.nom != null ? String(p.nom) : '';
            l.bindTooltip(nom);
            var html = '<b>Nom</b>: ' + nom + '<br><b>Libelle</b>: ' + (p.libellecourt != null ? String(p.libellecourt) : '') + '<br><b>Code UIC</b>: ' + (p.codes_uic != null ? String(p.codes_uic) : '');
            l.bindPopup(html, { maxWidth: 250 });
        }
        """)

        self.map.get_root().header.add_child(
            WEB_CHANNEL_SCRIPT_SRC, name="web_channel_script"
        )
        self.map.get_root().script.add_child(
            WEB_CHANNEL_INIT_JS, name="web_channel_init"
        )

        stations_cluster = MarkerCluster(name="Train Stations").add_to(self.map)

        stations_layer = folium.GeoJson(
            self.stations_geodataset,
            name="Train Stations",
            zoom_on_click=True,
            marker=folium.Marker(icon=Icons.STATION.value),
            on_each_feature=STATION_ON_EACH_FEATURE,
            style_function=lambda feature: {
                "fillColor": "#3388ff",
                "fillOpacity": 0.6,
                "color": "#3388ff",
                "weight": 2,
            },
            highlight_function=lambda feature: {
                "fillColor": "#3388ff",
                "fillOpacity": 0.9,
                "color": "#2266cc",
                "weight": 3,
            },
        )

        stations_search = Search(
            layer=stations_cluster,
            geom_type="Point",
            position="topleft",
            placeholder="Search for a station",
            search_zoom=13,
            collapsed=True,
            search_label="nom",
            color="#2266cc",
            weight=3,
            fillOpacity=0.9,
        )

        stations_search.add_to(self.map)

        stations_layer.add_to(stations_cluster)

        railways_features_group = folium.FeatureGroup(
            name="Railway Features", control=True
        )
        railways_features_group_name: str = railways_features_group.get_name()

        self.map.add_child(railways_features_group)

        def ligne_style(feature):
            t = feature.get("properties", {}).get("type_ligne") or ""
            color = TYPE_LIGNE_COLOR.get(t, DEFAULT_LIGNE_COLOR)
            return {"color": color, "weight": 2.5, "opacity": 0.85}

        def ligne_highlight(feature):
            t = feature.get("properties", {}).get("type_ligne") or ""
            color = TYPE_LIGNE_COLOR.get(t, DEFAULT_LIGNE_COLOR)
            return {"color": color, "weight": 4, "opacity": 1}

        railways_layer = folium.GeoJson(
            self.railways_geodataset,
            name="Lignes",
            zoom_on_click=True,
            style_function=ligne_style,
            highlight_function=ligne_highlight,
            popup_keep_highlighted=True,
            tooltip=folium.GeoJsonTooltip(
                fields=["lib_ligne", "type_ligne"], aliases=["Ligne", "Type"]
            ),
            popup=folium.GeoJsonPopup(
                fields=["lib_ligne", "code_ligne", "type_ligne"],
                aliases=["Ligne", "Code", "Type"],
            ),
        )

        railways_search = Search(
            layer=railways_layer,
            geom_type="Line",
            position="topleft",
            placeholder="Search for a railway",
            search_zoom=9,
            collapsed=True,
            search_label="lib_ligne",
            color=SEARCH_LIGNE_COLOR,
            weight=4,
            opacity=1,
        )

        railways_search.add_to(self.map)

        railways_layer.add_to(railways_features_group)

        milestones_low_zoom_layer = folium.GeoJson(
            self._milestones_low_zoom_for_map,
            name="MilestonesOnLowZoom",
            zoom_on_click=True,
            marker=folium.CircleMarker(
                radius=4,
                fill=True,
                fill_color="#ea580c",
                fill_opacity=0.9,
                color="#c2410c",
                weight=2,
            ),
            style_function=lambda f: {
                "fillColor": "#ea580c",
                "fillOpacity": 0.9,
                "color": "#c2410c",
                "weight": 2,
            },
            highlight_function=lambda f: {
                "fillColor": "#f97316",
                "fillOpacity": 1,
                "color": "#9a3412",
                "weight": 3,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["pk", "ligne", "type_reper"],
                aliases=["PK", "Ligne", "Type repère"],
            ),
            popup=folium.GeoJsonPopup(
                fields=["pk", "ligne", "code_ligne", "type_reper"],
                aliases=["PK", "Ligne", "Code ligne", "Type repère"],
            ),
            popup_keep_highlighted=True,
            control=False,
            show=False,
        )

        milestones_low_zoom_layer.add_to(railways_features_group)

        milestones_medium_zoom_layer = folium.GeoJson(
            self._milestones_medium_zoom_for_map,
            name="MilestonesOnMediumZoom",
            zoom_on_click=True,
            marker=folium.CircleMarker(
                radius=4,
                fill=True,
                fill_color="#ea580c",
                fill_opacity=0.9,
                color="#c2410c",
                weight=2,
            ),
            style_function=lambda f: {
                "fillColor": "#ea580c",
                "fillOpacity": 0.9,
                "color": "#c2410c",
                "weight": 2,
            },
            highlight_function=lambda f: {
                "fillColor": "#f97316",
                "fillOpacity": 1,
                "color": "#9a3412",
                "weight": 3,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["pk", "ligne", "type_reper"],
                aliases=["PK", "Ligne", "Type repère"],
            ),
            popup=folium.GeoJsonPopup(
                fields=["pk", "ligne", "code_ligne", "type_reper"],
                aliases=["PK", "Ligne", "Code ligne", "Type repère"],
            ),
            popup_keep_highlighted=True,
            control=False,
            show=False,
        )

        milestones_medium_zoom_layer.add_to(railways_features_group)

        self.map.get_root().script.add_child(folium.Element(f"""
        (function() {{
        var mapName = "{self.map.get_name()}";
        var milestonesLowZoomLayerName = "{milestones_low_zoom_layer.get_name()}";
        var milestonesMediumZoomLayerName = "{milestones_medium_zoom_layer.get_name()}";
        var railwaysLayerName = "{railways_layer.get_name()}";
        var railwaysFeaturesGroupName = "{railways_features_group_name}";
        var lowZoomThreshold = {self._milestones_visibility_settings["LOW"]["threshold"]};
        var mediumZoomThreshold = {self._milestones_visibility_settings["MEDIUM"]["threshold"]};

        function waitReady(tryCount) {{
            tryCount = tryCount || 0;

            var map = window[mapName];
            var milestonesLowZoomLayer = window[milestonesLowZoomLayerName];
            var milestonesMediumZoomLayer = window[milestonesMediumZoomLayerName];
            var railwaysLayer = window[railwaysLayerName];
            var railwaysFeaturesGroup = window[railwaysFeaturesGroupName];

            var mapOk = map && typeof map.getZoom === "function" && typeof map.on === "function";
            var milestonesLowZoomLayerOk = milestonesLowZoomLayer && typeof milestonesLowZoomLayer.addTo === "function" && typeof milestonesLowZoomLayer.remove === "function";
            var milestonesMediumZoomLayerOk = milestonesMediumZoomLayer && typeof milestonesMediumZoomLayer.addTo === "function" && typeof milestonesMediumZoomLayer.remove === "function";
            var railwaysLayerOk = railwaysLayer && typeof railwaysLayer.addTo === "function" && typeof railwaysLayer.remove === "function";
            var railwaysFeaturesGroupOk = railwaysFeaturesGroup && typeof railwaysFeaturesGroup.addTo === "function" && typeof railwaysFeaturesGroup.remove === "function";

            if (!(mapOk && milestonesLowZoomLayerOk && milestonesMediumZoomLayerOk && railwaysLayerOk && railwaysFeaturesGroupOk)) {{
                if (tryCount < 80) return setTimeout(function() {{ waitReady(tryCount + 1); }}, 100);
                console.warn("[milestones visibility] mapOk=", mapOk, "milestonesLowZoomLayerOk=", milestonesLowZoomLayerOk, "milestonesMediumZoomLayerOk=", milestonesMediumZoomLayerOk, "railwaysLayerOk=", railwaysLayerOk,
                    "map=", map,
                    "milestonesLowZoomLayer=", milestonesLowZoomLayer,
                    "milestonesMediumZoomLayer=", milestonesMediumZoomLayer,
                    "railwaysLayer=", railwaysLayer,
                    "railwaysFeaturesGroup=", railwaysFeaturesGroup);
                return;
            }}

            var prevZoom = null;
            var prevRailwaysLayer = null;
            var prevRailwaysFeaturesGroup = null;

            function updateLayerVisibility() {{
                var railwaysVisible = map.hasLayer(railwaysLayer);
                var railwaysFeaturesGroupVisible = map.hasLayer(railwaysFeaturesGroup);
                var z = map.getZoom();

                // Only proceed if state has changed (optimization)
                if (prevZoom === z && prevRailwaysLayer === railwaysVisible && prevRailwaysFeaturesGroup === railwaysFeaturesGroupVisible) return;
                prevZoom = z;
                prevRailwaysLayer = railwaysVisible;
                prevRailwaysFeaturesGroup = railwaysFeaturesGroupVisible;

                if (railwaysVisible && railwaysFeaturesGroupVisible) {{
                    if (z >= lowZoomThreshold) {{
                        if (!map.hasLayer(milestonesLowZoomLayer)) milestonesLowZoomLayer.addTo(map);
                        if (z >= mediumZoomThreshold) {{
                            if (!map.hasLayer(milestonesMediumZoomLayer)) milestonesMediumZoomLayer.addTo(map);
                        }} else {{
                            if (map.hasLayer(milestonesMediumZoomLayer)) map.removeLayer(milestonesMediumZoomLayer);
                        }}
                    }} else {{
                        if (map.hasLayer(milestonesLowZoomLayer)) map.removeLayer(milestonesLowZoomLayer);
                        if (map.hasLayer(milestonesMediumZoomLayer)) map.removeLayer(milestonesMediumZoomLayer);
                    }}
                }} else {{
                    if (map.hasLayer(milestonesLowZoomLayer)) map.removeLayer(milestonesLowZoomLayer);
                    if (map.hasLayer(milestonesMediumZoomLayer)) map.removeLayer(milestonesMediumZoomLayer);
                }}
            }}

            // Initial check
            updateLayerVisibility();
            // Event listeners
            map.on("zoomend", updateLayerVisibility);
            map.on("overlayadd", function(e) {{
                if (e.layer === railwaysLayer) updateLayerVisibility();
                if (e.layer === railwaysFeaturesGroup) updateLayerVisibility();
            }});
            map.on("overlayremove", function(e) {{
                if (e.layer === railwaysLayer) updateLayerVisibility();
                if (e.layer === railwaysFeaturesGroup) updateLayerVisibility();
            }});
        }}

        waitReady();
        }})();
        """))

        Fullscreen(
            position="topright",
            title="Fullscreen",
            title_cancel="Exit",
            force_separate_button=True,
        ).add_to(self.map)

        MousePosition(
            position="bottomright",
            separator=" | ",
            prefix="",
            lat_formatter="function(num) {return 'Latitude: ' + num}",
            lng_formatter="function(num) {return 'Longitude: ' + num}",
        ).add_to(self.map)

        folium.LayerControl().add_to(self.map)

        self.map.get_root().script.add_child(
            on_marker_clicked_js_code(milestones_low_zoom_layer.get_name())
        )
        self.map.get_root().script.add_child(
            on_marker_clicked_js_code(milestones_medium_zoom_layer.get_name())
        )

    def to_html(self, path: Path, prefix: str = "") -> Path:
        """Write the Folium map to disk and return the HTML file path."""
        output_dir = Path(path)
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_dir / f"{prefix}.html"
        self.map.save(html_path)
        try:
            size_bytes = html_path.stat().st_size
        except OSError as e:
            logger.warning(
                "Saved map HTML but could not stat file",
                path=str(html_path),
                error=str(e),
            )
        else:
            logger.info(
                "Map HTML written",
                path=str(html_path),
                size_bytes=size_bytes,
            )
        return html_path
