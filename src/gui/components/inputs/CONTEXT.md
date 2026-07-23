# Input component context

## Purpose

This package provides OTP/IP/port entry and reusable selection-field controls.

## Boundaries and philosophy

- Keep validation local and deterministic while leaving domain authentication and
  device operations to owners and controllers.
- Preserve paste, backspace, focus traversal, placeholder, and clear behavior.
- Use typed slots for connected handlers and avoid anonymous signal targets.
- Keep validation and selection states accessible and theme-aware.
- Keep sizes and constraints in `input_settings.py`.

## Primary dependencies

- **PySide6** supplies line edits, validators, combo boxes, focus events, and slots.
- Shared icons, colors, and component lifecycle provide infrastructure.
- **pytest** and **pytest-qt** verify validation, focus, paste, selection, and
  screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/inputs/tests`; appearance changes require
  input screenshot tests and visual inspection.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
