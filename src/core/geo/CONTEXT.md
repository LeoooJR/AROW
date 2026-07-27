# Geospatial context

## Purpose

`core.geo` owns railway and station datasets, schemas, geometry, locations,
milestones, map icons, the Qt web-channel bridge, and Folium map rendering.

## Boundaries and philosophy

- Treat pandas and GeoPandas structures as columnar data. Prefer vectorized
  operations, joins, concatenation, aggregations, and spatial joins over
  `iterrows`, row-wise Python `apply`, or manual index loops.
- Isolate and explain any unavoidable scalar loop required by a third-party API.
- Validate dataset shape, dtypes, columns, geometry, and values with reusable
  Pandera schemas at load, export, and map-pipeline boundaries.
- Translate schema failures into explicit project exceptions following
  `SchemaValidationError` conventions.
- Build server-side map HTML with Folium. Prepare and simplify display data in
  Python, keep first paint fast, and avoid redundant layers or inline assets.
- Keep Leaflet/Qt bridge code isolated from domain geometry and dataset logic.

## Primary dependencies

- **pandas** and **GeoPandas** provide columnar and spatial data operations.
- **Pandera** defines dataset contracts.
- **Shapely** provides geometry values and transformations.
- **Folium** and **xyzservices** produce map HTML and tile configuration.
- **pytest** verifies datasets, schemas, geometry, locations, and rendering.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/core/geo/tests` plus affected render-map work and map
  controller tests.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Architecture and map stack: [`../../../README.md`](../../../README.md).
