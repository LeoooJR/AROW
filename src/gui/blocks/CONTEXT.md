# GUI blocks context

## Purpose

`gui.blocks` contains reusable, multi-component view units that own a coherent
piece of presentation and interaction behavior.

## Boundaries and philosophy

- Put a block in the category that owns its behavior and keep owner-specific
  helpers and frozen settings beside it.
- Lifecycle-aware blocks inherit `Block`, implement its hooks, and call
  `_finalize_ui_hooks()` only after children and state are initialized.
- Blocks own filtering, selection, placeholders, theme propagation, rendering,
  and local signal handlers. Panels interact through explicit public methods
  rather than chained access to block internals.
- Prefer owner-local `Text` and `UI` dataclasses for stable copy and meaningful
  child references.
- Export reusable blocks from the owning category and this package when they are
  intended for project-wide use.

## Primary dependencies

- **PySide6** provides widget composition, painting, models, signals, and slots.
- `gui.components`, shared wrappers, settings, icons, colors, and signals provide
  reusable GUI primitives.
- **pytest** and **pytest-qt** test block behavior and screenshots.

Versions remain in `pyproject.toml`.

## Validation and references

- Keep block-internal tests in the owning category's `tests` directory; panel and
  cross-block integration tests remain under `src/gui/tests`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Design system: [`../../../DESIGN.md`](../../../DESIGN.md).
