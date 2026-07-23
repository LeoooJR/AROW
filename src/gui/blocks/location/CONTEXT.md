# Location block context

## Purpose

This package presents the currently targeted railway milestone and its location
metadata.

## Boundaries and philosophy

- Treat milestone data as view input; validation and geospatial computation belong
  in `core.geo` and `core.work`.
- Render missing or partial metadata deliberately without inventing domain values.
- Keep theme changes and icons within the shared GUI resource system.
- Keep owner-specific layout values in `location_settings.py`.

## Primary dependencies

- **PySide6** provides layouts and labels.
- Shared label, indicator, icon, and wrapper primitives provide presentation.
- **pytest** and **pytest-qt** verify milestone rendering and state transitions.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/location/tests` plus affected map or simulation
  integration tests.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
