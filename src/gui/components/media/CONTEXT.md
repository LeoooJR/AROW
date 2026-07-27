# Media component context

## Purpose

This package provides reusable raster-image and SVG rendering components.

## Boundaries and philosophy

- Load media through Qt resource or explicit application paths and fail
  predictably when assets are invalid.
- Preserve aspect ratio, transparent backgrounds, device-pixel behavior, and
  theme-aware resource selection.
- Keep painting and renderer ownership local to the component.
- Keep SVG defaults in `svg_settings.py`; resource registration remains owned by
  the parent GUI package.

## Primary dependencies

- **PySide6** supplies pixmaps, painters, labels, sizes, and `QSvgRenderer`.
- Shared resource and component lifecycle helpers provide infrastructure.
- **pytest** and **pytest-qt** verify loading, sizing, rendering, and screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/media/tests`; appearance changes require
  media screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
