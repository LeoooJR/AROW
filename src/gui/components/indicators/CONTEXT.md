# Indicator component context

## Purpose

This package provides progress, condition, dot-status, and text-status indicators
with shared semantic states.

## Boundaries and philosophy

- Keep status kinds explicit and map them consistently to shared semantic colors.
- Indicators render state supplied by owners and do not infer domain readiness.
- Preserve accessible text alongside color; color alone must not carry meaning.
- Keep animation and dimensions in `indicator_settings.py`.

## Primary dependencies

- **PySide6** supplies frames, labels, progress bars, and animations.
- Shared colors and stylesheet rules provide semantic presentation.
- **pytest** and **pytest-qt** verify state mapping, progress, animation, and
  screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/indicators/tests`; appearance changes
  require indicator screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
