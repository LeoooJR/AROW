# Application source context

## Purpose

`src` contains AROW's executable Python application. The application is split into
CLI composition (`commands`), UI orchestration (`controller`), domain and model
logic (`core`), and the PySide6 view (`gui`).

## Boundaries and philosophy

- Read this file after the repository-level `AGENTS.md`, then read each
  `CONTEXT.md` on the path to the package being changed. A nearer context refines
  this one but never overrides `AGENTS.md`.
- Keep entrypoints and logging bootstrap thin. Business behavior belongs in
  `core`, UI intent routing in `controller`, and presentation in `gui`.
- Preserve the MVC boundaries and prefer small, typed interfaces between layers.
- Tests and non-Python assets inherit the nearest production-package context.

## Logging policy

- GUI `INFO` records describe explicit user workflow actions; presentation and
  forwarded outcomes are silent or `DEBUG`.
- The layer that produces a domain outcome owns its `INFO`, `WARNING`, or `ERROR`
  record. Controllers log routing at `DEBUG` and orchestration anomalies at
  `WARNING` or `ERROR`.
- Use concise messages with structured context instead of class prefixes,
  interpolated values, or multiline object dumps. Expected skips and coalescing
  are `DEBUG`; recoverable degradation is `WARNING`; terminal failure is `ERROR`
  or `exception` when a traceback is useful.
- Use standard Loguru levels rather than `success`, and pass sensitive values only
  through structured fields covered by the logger redaction policy.

## Primary dependencies

- **Typer** composes the command-line entrypoint.
- **PySide6** provides the desktop runtime.
- **Loguru** provides application and worker logging.
- **pytest** and **pytest-qt** provide deterministic unit and Qt behavior tests.

Dependency versions and groups are owned by `pyproject.toml`.

## Validation and references

- Run the nearest package tests for behavior changes; cross-layer changes require
  the full `uv run pytest` suite.
- Application architecture and launch modes: [`../README.md`](../README.md).
- Repository-wide policy and validation: [`../AGENTS.md`](../AGENTS.md).
