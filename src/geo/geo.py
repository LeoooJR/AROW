from pathlib import Path
from typing import Literal

import folium
import geopandas
import pandas as pd
from datasets import DatasetManager
from folium.plugins import Fullscreen, MarkerCluster, MousePosition
from folium.utilities import JsCode
from icons import Icons
from shapely import Point


class MapRenderer:

    DEFAULT_LATITUDE: float = 46.232193

    DEFAULT_LONGITUDE: float = 2.209667

    CRS_FRANCE: str = "EPSG:2154"

    def __init__(self):

        self.map = folium.Map(
            location=(self.DEFAULT_LATITUDE, self.DEFAULT_LONGITUDE), zoom_start=6
        )

        self._load_datasets()

        self._create_layers()

    def _load_datasets(self):

        manager: DatasetManager = DatasetManager()

        stations_geodataset: geopandas.GeoDataFrame = manager.read("gares-de-voyageurs")
        stations_geodataset: geopandas.GeoDataFrame = stations_geodataset.drop(
            columns="position_geographique"
        )
        self.stations_geodataset: geopandas.GeoDataFrame = stations_geodataset.astype(
            {"segment_drg": "category"}
        )

        railways_geodataset = manager.read(id="lignes-par-type")
        railways_geodataset: geopandas.GeoDataFrame = railways_geodataset.astype(
            {"type_ligne": "category"}
        )
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

        milestones_dataset: pd.DataFrame = manager.read(
            id="referentiel_pk_gps", encoding="latin-1"
        )
        milestones_dataset.columns = milestones_dataset.columns.map(lambda c: c.lower())
        milestones_dataset: pd.DataFrame = milestones_dataset.astype(
            {"type_reper": "category", "ligne": "category", "code_ligne": "category"}
        )
        milestones_dataset["geometry"] = milestones_dataset.apply(
            lambda row: Point(
                float(row.longitude.replace(",", ".")),
                float(row.latitude.replace(",", ".")),
            ),
            axis=1,
        )
        milestones_dataset: pd.DataFrame = milestones_dataset.drop(
            columns=["latitude", "longitude"]
        )

        # Parse PK string (e.g. "001+000" -> 1.0 km, "012+500" -> 12.5 km)
        def parse_milestones_code(milestone: str) -> float:
            if pd.isna(milestone):
                return float("nan")
            parts = str(milestone).strip().split("+")
            if len(parts) != 2:
                return float("nan")
            try:
                km, m = int(parts[0]), int(parts[1])
                return km + m / 1000.0
            except ValueError:
                return float("nan")

        milestones_dataset["kilometers"] = milestones_dataset["pk"].map(
            parse_milestones_code
        )
        milestones_dataset = milestones_dataset.dropna(
            subset=["geometry", "code_ligne", "kilometers"]
        )
        self.milestones_geodataset: geopandas.GeoDataFrame = geopandas.GeoDataFrame(
            milestones_dataset, crs="EPSG:4326"
        )
        milestones_kilometer_geodataset: geopandas.GeoDataFrame = (
            self.milestones_geodataset[
                self.milestones_geodataset["type_reper"] == "Kilomètre"
            ]
        )

        self._milestones_visibility_settings: dict = {
            "LOW": {"threshold": 10, "spacing": 10.0, "tolerance": 0.5},
            "MEDIUM": {"threshold": 14, "spacing": 1.0, "tolerance": 0.05},
        }

        def at_distance(kilometer: float, settings: Literal["LOW", "MEDIUM"]) -> bool:
            spacing: float = self._milestones_visibility_settings[settings]["spacing"]
            tolerance: float = self._milestones_visibility_settings[settings][
                "tolerance"
            ]
            remainder = kilometer % spacing
            return remainder <= tolerance or (spacing - remainder) <= tolerance

        subset_indices = []
        for _code_ligne, group in milestones_kilometer_geodataset.groupby(
            "code_ligne", observed=True
        ):
            group = group.sort_values("kilometers")
            if not group.empty:
                for idx, row in group.iterrows():
                    km = row["kilometers"]
                    if at_distance(kilometer=km, settings="LOW"):
                        subset_indices.append(idx)

        self._milestones_low_zoom_geodataset: geopandas.GeoDataFrame = (
            milestones_kilometer_geodataset.loc[sorted(subset_indices)]
        )
        self._milestones_medium_zoom_geodataset: geopandas.GeoDataFrame = (
            milestones_kilometer_geodataset.drop(index=subset_indices)
        )
        self._milestone_high_zoom_geodataset: geopandas.GeoDataFrame = (
            self.milestones_geodataset[
                self.milestones_geodataset["type_reper"] != "Kilomètre"
            ]
        )

    def _create_layers(self):

        STATION_ON_EACH_FEATURE = JsCode("""
        function(f, l) {
            var p = f.properties || {};
            var nom = p.nom != null ? String(p.nom) : '';
            l.bindTooltip(nom);
            var html = '<b>Nom</b>: ' + nom + '<br><b>Libelle</b>: ' + (p.libellecourt != null ? String(p.libellecourt) : '') + '<br><b>Code UIC</b>: ' + (p.codes_uic != null ? String(p.codes_uic) : '');
            l.bindPopup(html, { maxWidth: 250 });
        }
        """)

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

        stations_layer.add_to(stations_cluster)

        railways_features_group = folium.FeatureGroup(
            name="Railway Features", control=True
        )
        railways_features_group_name: str = railways_features_group.get_name()

        self.map.add_child(railways_features_group)

        DEFAULT_LIGNE_COLOR = "#94a3b8"  # unknown – light slate

        TYPE_LIGNE_COLOR = {
            "Ligne proprement dite": "#1e3a5f",  # main line – dark blue
            "Raccordement": "#64748b",  # siding/connection – slate
            "Voie-mère d'embranchement": "#059669",  # branch – emerald
            "Voie de desserte de voies ferrées de port": "#b45309",  # port access – amber
        }

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

        railways_layer.add_to(railways_features_group)

        milestones_low_zoom_layer = folium.GeoJson(
            self._milestones_low_zoom_geodataset,
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
            self._milestones_medium_zoom_geodataset,
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

    def to_html(self, prefix: str = ""):

        self.map.save(f"{prefix}.html")


if __name__ == "__main__":

    manager: MapRenderer = MapRenderer()

    manager.to_html(prefix="map")
