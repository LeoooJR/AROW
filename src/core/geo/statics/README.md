# Geo static dataset storage

Packaged geo assets under this directory are versioned in git.

## Current policy

- `pk.sqlite` remains in git because it is relatively small and required for offline PK lookups.
- GeoJSON assets (`gares-de-voyageurs.geojson`, `lignes-par-type.geojson`) stay in git with SHA-256 catalog hashes enforced by `DatasetManager`.

## Future options

If repository size or binary diff noise grows, larger or additional SQLite databases may move to Git LFS. Any migration should preserve the hash-verification contract in `src/core/geo/datasets.py` and update catalog hashes accordingly.
