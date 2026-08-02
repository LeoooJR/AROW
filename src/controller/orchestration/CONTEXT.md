# Application orchestration context

## Purpose

`controller.orchestration` owns top-level application wiring, shared runner
lifetime, startup sequencing, and orderly shutdown.

## Boundaries and philosophy

- `AppController` composes domain subcontrollers and owns the shared
  `AsyncRunner`; it does not absorb domain-specific behavior.
- Keep startup and shutdown ordering explicit, bounded, and safe if work is still
  pending.
- Bind application-level view signals through named, typed slots.
- Ensure executor cleanup and Qt event processing cannot leave active jobs,
  duplicate callbacks, or late UI updates.

## Primary dependencies

- **PySide6** provides application lifecycle, timers, slots, and event-loop
  integration.
- Controller runner and domain subcontrollers provide the orchestration units.
- **pytest** and **pytest-qt** verify startup, shutdown, timeout, and cleanup paths.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/controller/orchestration/tests src/controller/tests`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Controller and startup flows:
  [`../../../docs/HOW_TO_controller_and_signals.md`](../../../docs/HOW_TO_controller_and_signals.md).
