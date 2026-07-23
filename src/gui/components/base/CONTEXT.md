# Component base context

## Purpose

This package defines the lifecycle contract shared by reusable GUI components and
the Qt/ABC metaclass bridge.

## Boundaries and philosophy

- Keep `Component` independent of concrete widgets and domain behavior.
- Lifecycle hooks cover size policy, alignment, signal binding, and theme-icon
  application.
- Subclasses call `_finalize_ui_hooks()` once, after every referenced child and
  state value exists.
- Changes to this contract affect all component categories and require broad GUI
  validation.

## Primary dependencies

- **PySide6** supplies `QObject` and Qt metaclass behavior.
- Python **abc** defines the lifecycle contract.
- **pytest** and **pytest-qt** verify hook order and subclass behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/gui/components/base/tests` followed by affected component
  tests; contract changes require the full GUI suite.
- Parent rules: [`../CONTEXT.md`](../CONTEXT.md).
- Visual direction: [`../../../../DESIGN.md`](../../../../DESIGN.md).
