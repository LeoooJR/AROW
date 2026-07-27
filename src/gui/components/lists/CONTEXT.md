# List component context

## Purpose

This package provides the reusable styled list widget used by higher-level GUI
blocks.

## Boundaries and philosophy

- Keep the list generic; item semantics, filtering, and domain selection belong to
  the owning block.
- Preserve predictable sizing, scrolling, spacing, selection, and empty behavior.
- Use Qt item/model APIs and public methods rather than reaching into viewport
  internals from owners.
- Keep dimensions in `list_settings.py` and styling in the shared stylesheet.

## Primary dependencies

- **PySide6** supplies list widgets, items, fonts, sizing, and selection behavior.
- Shared component lifecycle and styling provide infrastructure.
- **pytest** and **pytest-qt** verify item behavior, sizing, and selection.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/lists/tests` plus affected block tests.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
