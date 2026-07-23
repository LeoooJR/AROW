# Card block context

## Purpose

This package presents host identity and ADB bridge status as reusable card-style
blocks with structured metadata rows.

## Boundaries and philosophy

- Render state supplied through public update methods; do not perform host or ADB
  discovery in widgets.
- Keep identity and bridge sections visually parallel where their semantics match.
- Preserve explicit status states and readable metadata when values are missing.
- Keep card-specific dimensions in `card_settings.py` and shared styling in the
  GUI stylesheet.

## Primary dependencies

- **PySide6** provides card layouts and labels.
- Shared indicators, labels, containers, icons, and wrappers provide primitives.
- **pytest** and **pytest-qt** verify state rendering and card behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/card/tests`; appearance changes also require
  its nearest screenshot coverage.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
