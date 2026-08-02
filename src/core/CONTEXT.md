# Core context

## Purpose

`core` contains AROW's model entrypoint, domain state, signal bus, persistence,
network boundary, Qt-facing models, and executable work definitions.

## Boundaries and philosophy

- Keep model and domain behavior independent of concrete GUI widgets and panels.
- Keep network logic in `network.py`, device behavior in `devices`, ADB protocol
  and subprocess calls in `adb`, geospatial work in `geo`, and blocking operations
  in `work`.
- Publish model changes through the core signal bus and typed payloads rather than
  importing GUI signals.
- Prefer Qt model classes in `qt_models.py` when views need list, table, or tree
  ownership; avoid passing mutable plain collections across the controller
  boundary when a model is clearer.
- Preserve explicit persistence and stale-state cleanup semantics.

## Primary dependencies

- **PySide6** supplies Qt models used at the view boundary.
- **Loguru** supplies model and repository logging.
- Domain subpackages add their own ADB and geospatial dependencies.
- **pytest** verifies entrypoint, signal, simulation, and repository behavior.

Versions remain in `pyproject.toml`.

## Validation and references

- Run affected tests under `src/core/tests` and the owning subpackage. Shared API
  changes require `uv run pytest`.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Architecture: [`../../README.md`](../../README.md).
- Simulation persistence:
  [`../../docs/HOW_TO_simulation_persistence.md`](../../docs/HOW_TO_simulation_persistence.md).
