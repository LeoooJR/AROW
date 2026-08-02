# Controller context

## Purpose

`controller` translates view intent into model work, runs blocking operations away
from the Qt main thread, and routes model outcomes back to the view.

## Boundaries and philosophy

- Controllers orchestrate; domain behavior and I/O belong in `core`.
- Submit blocking work through `AsyncRunner` with `JobSpecification`; do not add
  ad-hoc threads or processes.
- Use returned `JobHandler` values and `runner.bind_handle_signals(handle)` for
  per-job progress, cancellation, and completion.
- Treat cancellation, cleanup, stale results, and shutdown as explicit lifecycle
  behavior. Coalesced or cancelled results must not update current UI state.
- Custom methods connected through Qt `.connect(...)` or `QTimer.singleShot(...)`
  use matching typed `@Slot(...)` signatures. Core-bus subscriptions remain plain
  Python methods.

## Primary dependencies

- **PySide6** provides queued signals, timers, and main-thread integration.
- Python **concurrent.futures** supplies thread and process executors.
- **Loguru** carries structured logs across controller and worker boundaries.
- **pytest** and **pytest-qt** test success, failure, cancellation, cleanup, and
  stale-result behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run targeted tests under `src/controller/tests` plus the affected domain or
  orchestration tests. Cross-layer changes require `uv run pytest`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Async work contract: [`../../docs/HOW_TO_async_jobs.md`](../../docs/HOW_TO_async_jobs.md).
- Signal and controller flows:
  [`../../docs/HOW_TO_controller_and_signals.md`](../../docs/HOW_TO_controller_and_signals.md).
