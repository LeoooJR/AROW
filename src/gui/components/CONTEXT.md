# GUI components context

## Purpose

`gui.components` contains reusable, focused GUI primitives grouped by interaction
or presentation role.

## Boundaries and philosophy

- Components remain generic and domain-light; compose several components into a
  block when behavior becomes owner-specific.
- Lifecycle-aware components inherit `Component`, implement its hooks, and call
  `_finalize_ui_hooks()` only after children and state are initialized.
- Reuse shared colors, stylesheet rules, icons, animations, and layout wrappers.
  Keep category-specific sizes in frozen settings dataclasses.
- Export reusable components from their category and this package when intended
  for project-wide use.
- Preserve object names, signal contracts, focus behavior, and theme propagation
  as part of a component's public behavior.

## Primary dependencies

- **PySide6** provides widgets, validation, painting, SVG, signals, and slots.
- Shared GUI infrastructure supplies colors, styling, resources, and layouts.
- **pytest** and **pytest-qt** provide behavioral and offscreen screenshot tests.

Versions remain in `pyproject.toml`.

## Validation and references

- Keep component tests in the owning category's `tests` directory. Appearance
  changes require the nearest screenshot test and visual inspection.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Design system: [`../../../DESIGN.md`](../../../DESIGN.md).
