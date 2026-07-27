# Dialog component context

## Purpose

This package wraps file selection and application message dialogs with consistent
defaults and icon treatment.

## Boundaries and philosophy

- Keep dialogs synchronous only where the existing Qt API requires it and return
  explicit user choices to the caller.
- Do not perform file I/O beyond selecting a path.
- Preserve cancellation as a normal outcome and keep parent ownership explicit.
- Use shared icons, object names, and stylesheet rules instead of local styles.
- Keep dialog dimensions in `dialog_settings.py`.

## Primary dependencies

- **PySide6** supplies file and message dialogs, icons, and sizing.
- Shared resource helpers provide application iconography.
- **pytest** and **pytest-qt** verify options, cancellation, results, and layout.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/dialogs/tests`; appearance changes require
  the nearest dialog or integration screenshot.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
