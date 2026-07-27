# Start block context

## Purpose

This package builds the start experience: connection actions, operator readiness,
recent-session content and empty state, and the guided walkthrough.

## Boundaries and philosophy

- Present readiness from established GUI signals and public state updates; do not
  query ADB or persistence directly.
- Keep start actions as view intent and let controllers perform model work.
- Make empty, ready, degraded, and active states explicit and keyboard-readable.
- Reuse shared components and wrappers rather than introducing local duplicates.
- Keep start-specific sizing in `start_settings.py`.

## Primary dependencies

- **PySide6** supplies layouts, painting, signals, and slots.
- Shared buttons, indicators, labels, containers, and wrappers provide primitives.
- **pytest** and **pytest-qt** verify readiness, actions, placeholders, and layout.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/start/tests` plus affected welcome and
  main-window tests.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
