# Core work context

## Purpose

`core.work` defines blocking model operations submitted by controllers and the
typed outcomes applied on the Qt main thread.

## Boundaries and philosophy

- Implement worker behavior as `CoreRuntimeWork`: immutable inputs, blocking
  `run()`, and a typed `CoreRuntimeWorkOutcome`.
- Worker code performs I/O or computation and returns data; it must not mutate Qt
  widgets or main-thread model state.
- Apply outcomes through registered `apply_main_thread` handlers and failures
  through `apply_failure_main_thread`, dispatched by `ModelEntrypoint`.
- Keep work registration explicit in the work repository and keep outcome types
  safe for their selected thread or process executor.
- Maintain the focused companion Markdown specifications for workflows that have
  them.

## Primary dependencies

- Core entrypoint protocols and signal payloads define the application boundary.
- ADB, device, simulation, and geo packages supply domain operations.
- **Shapely** supports marker-location validation where needed.
- **pytest** verifies `run`, apply, and failure paths with mocked I/O.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/core/work/tests` plus affected `src/core/tests` and domain
  controller tests.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Complete async contract:
  [`../../../docs/HOW_TO_async_jobs.md`](../../../docs/HOW_TO_async_jobs.md).
- Persistence behavior:
  [`../../../docs/HOW_TO_simulation_persistence.md`](../../../docs/HOW_TO_simulation_persistence.md).
