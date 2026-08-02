# Device block context

## Purpose

This package renders device rows, badges, empty state, selection, refresh status,
removal intent, and attention guidance.

## Boundaries and philosophy

- Consume Qt device models and established GUI signals; never discover or mutate
  devices directly.
- Keep stable device identity separate from display state and transient selection.
- Preserve selection and item presentation when models refresh or operations
  complete out of order.
- Bound timers and highlight animations to visible, valid widgets.
- Keep device-specific layout and timing in `device_settings.py`.

## Primary dependencies

- **PySide6** supplies item views, timers, events, signals, and slots.
- Core Qt models and shared GUI components provide data and presentation
  primitives.
- **pytest** and **pytest-qt** verify model updates, selection, signals, and timers.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/device/tests` plus affected device-panel tests
  under `src/gui/tests`.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Signal flows:
  [`../../../../docs/HOW_TO_controller_and_signals.md`](../../../../docs/HOW_TO_controller_and_signals.md).
