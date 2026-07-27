# Label component context

## Purpose

This package provides reusable helper, emphasized, and leading-icon text labels.

## Boundaries and philosophy

- Keep labels presentation-only and preserve normal Qt text and accessibility
  behavior.
- Use shared font, color, icon, and stylesheet systems rather than local styles.
- Keep alignment, wrapping, elision, and theme-icon behavior explicit.
- Avoid owner-specific copy or domain state in reusable label classes.

## Primary dependencies

- **PySide6** supplies labels, fonts, layouts, and alignment.
- Shared fonts, icons, colors, and component lifecycle provide infrastructure.
- **pytest** and **pytest-qt** verify typography, icons, alignment, and screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/labels/tests`; appearance changes require
  label screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
