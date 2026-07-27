# Button component context

## Purpose

This package provides reusable primary, tool, and walkthrough button variants.

## Boundaries and philosophy

- Expose normal Qt click and action semantics; domain intent is connected by the
  owning block or panel.
- Preserve keyboard focus, enabled state, icon sizing, and accessible labels.
- Resolve icons through shared resource helpers and propagate theme changes.
- Keep button dimensions in `button_settings.py` and visual states in the shared
  stylesheet.

## Primary dependencies

- **PySide6** supplies push buttons, tool buttons, icons, and events.
- Shared icons, colors, and component lifecycle provide infrastructure.
- **pytest** and **pytest-qt** verify interaction, sizing, and theme behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/buttons/tests`; appearance changes require
  the nearest screenshot coverage.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
