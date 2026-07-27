# Domain subcontroller context

## Purpose

`controller.domains` contains focused subcontrollers for application, ADB, map,
and simulation workflows.

## Boundaries and philosophy

- Each subcontroller owns one workflow's view-signal bindings, job tracking,
  post-apply chaining, cancellation, and cleanup.
- Translate view payloads into model work and expose results through established
  view methods and signals; do not reach into block internals.
- Register core-runtime completion and failure through
  `ModelEntrypoint.apply_result` and `ModelEntrypoint.apply_failure`.
- Guard asynchronous callbacks against stale handles and state changes.
- Cover success, failure, cancellation, cleanup, and stale-result behavior where
  the workflow supports them.

## Primary dependencies

- **PySide6** provides typed slots and timers at the view boundary.
- Controller runner types coordinate asynchronous work.
- **pytest** and **pytest-qt** test subcontrollers with mocked model and ADB
  boundaries.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/controller/domains/tests` plus affected core-work tests.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Controller and signal flows:
  [`../../HOW_TO_controller_and_signals.md`](../../HOW_TO_controller_and_signals.md).
- Simulation persistence:
  [`../../HOW_TO_simulation_persistence.md`](../../HOW_TO_simulation_persistence.md).
