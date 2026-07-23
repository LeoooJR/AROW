# Activity block context

## Purpose

This package renders the activity timeline, date grouping, filtering, selection,
event metadata, and current log-file presentation.

## Boundaries and philosophy

- Keep activity entries typed and rendering deterministic from entry state.
- Preserve filtering and selection when events are added, removed, or rerendered.
- Keep dynamic sizing and deferred layout refresh bounded and safe after widget
  destruction.
- Translate established GUI signals into activity entries without initiating
  model work.
- Keep layout and timing values in `activity_log_settings.py`.

## Primary dependencies

- **PySide6** supplies list items, menus, layouts, timers, and slots.
- Shared list, file-display, label, and button components provide primitives.
- **pytest** and **pytest-qt** verify filtering, signals, sizing, and presentation.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/activity/tests` plus affected activity-panel
  integration tests under `src/gui/tests`.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
