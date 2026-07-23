# Map block context

## Purpose

This package owns the embedded map canvas, coordinate display, legend, selected
location presentation, and loading, failure, and device-required placeholders.

## Boundaries and philosophy

- Display map HTML and bridge events supplied by controllers; Folium rendering and
  geospatial validation stay in `core.geo`.
- Represent loading, unavailable-device, render-failure, and ready states
  explicitly and transition between them without stale content.
- Route user-selected coordinates through categorized GUI signals.
- Keep web-channel behavior narrow and do not embed model or ADB operations in the
  view.
- Keep map-specific sizes in `map_settings.py`.

## Primary dependencies

- **PySide6** supplies widgets and the embedded web view/channel integration.
- Shared placeholders, labels, icons, and wrappers provide presentation.
- **pytest** and **pytest-qt** verify map state, bridge signals, and placeholders.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/map/tests` plus affected map-panel, map
  controller, render-work, and geo tests.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
