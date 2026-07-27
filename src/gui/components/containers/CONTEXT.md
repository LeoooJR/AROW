# Container component context

## Purpose

This package provides reusable group boxes, placeholders, and the authentication
card container.

## Boundaries and philosophy

- Containers own composition and local validation feedback, not ADB operations or
  controller orchestration.
- Emit user intent through established GUI signals and keep transient timers
  bounded to widget lifetime.
- Preserve clear empty, invalid, and attention states without inline styling.
- Keep sizing and animation constants in `container_settings.py`.

## Primary dependencies

- **PySide6** supplies frames, layouts, timers, validation events, and slots.
- Shared inputs, labels, buttons, icons, and wrappers provide primitives.
- **Loguru** records non-sensitive UI diagnostics.
- **pytest** and **pytest-qt** verify validation, timers, composition, and
  screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/containers/tests`; appearance changes
  require the container screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
