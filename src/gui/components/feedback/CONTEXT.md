# Feedback component context

## Purpose

This package provides transient, non-blocking feedback such as animated toasts.

## Boundaries and philosophy

- Feedback reports outcomes supplied by owners; it does not initiate work.
- Keep animation, placement, timeout, and destruction safe when parent windows
  move, close, or disappear.
- Use semantic success, warning, and error presentation from shared colors and
  styles.
- Keep timing and dimensions in `feedback_settings.py`.

## Primary dependencies

- **PySide6** supplies top-level widgets, screen geometry, timers, and property
  animations.
- Shared colors and animation conventions provide visual semantics.
- **pytest** and **pytest-qt** verify lifecycle, placement, timing, and screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/feedback/tests`; appearance changes
  require the toast screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
