# Block base context

## Purpose

This package defines the abstract lifecycle contract shared by GUI blocks and the
Qt/ABC metaclass bridge.

## Boundaries and philosophy

- Keep `Block` independent of concrete widgets and domain behavior.
- Lifecycle hooks cover size policy, alignment, signal binding, and theme-icon
  application.
- Subclasses call `_finalize_ui_hooks()` once, after all referenced child widgets
  and state exist.
- Changes to this contract affect every block and require broad GUI validation.

## Primary dependencies

- **PySide6** supplies `QObject` and Qt metaclass behavior.
- Python **abc** defines the lifecycle contract.
- **pytest** and **pytest-qt** verify hook order and subclass behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/blocks/base/tests` followed by affected block tests;
  contract changes require the full GUI suite.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
