# Top-bar block context

## Purpose

This package owns application-level navigation and top-bar controls, including
panel visibility and theme actions.

## Boundaries and philosophy

- Emit categorized view intent; do not manipulate controllers or model state
  directly.
- Use explicit display and hide signals for sidebars, never boolean toggle
  protocols.
- Keep theme icons synchronized with the active theme and Qt resource helpers.
- Preserve compact keyboard-accessible controls and stable object names used by
  styling and tests.
- Keep top-bar dimensions in `top_bar_settings.py`.

## Primary dependencies

- **PySide6** supplies controls, actions, signals, slots, and animations.
- Shared buttons, icons, colors, signals, and wrappers provide primitives.
- **pytest** and **pytest-qt** verify actions, visibility signals, theme state, and
  screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/top_bar/tests`; appearance changes require its
  screenshot test and shell changes require the full-window screenshot.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
