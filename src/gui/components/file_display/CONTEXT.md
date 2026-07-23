# File-display component context

## Purpose

This package presents a selected or generated file path and related file actions
in a compact reusable row.

## Boundaries and philosophy

- Treat paths as display input and emit actions to the owner; do not own log
  persistence or file generation.
- Elide long paths predictably while preserving the full value for access and
  tooltips.
- Keep delayed layout refresh safe after widget destruction.
- Use shared icons, labels, signals, and stylesheet rules.

## Primary dependencies

- **PySide6** supplies labels, layouts, font metrics, timers, and slots.
- Shared button and icon components provide actions.
- **pytest** and **pytest-qt** verify path updates, elision, actions, and sizing.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/file_display/tests` plus affected activity
  log integration tests.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
