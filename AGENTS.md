# AROW Project Instructions

## Project overview

- AROW is a PySide6 desktop application that spoofs an Android phone's
  coordinates through Android Debug Bridge (`ADB`).
- The application follows an MVC split:
  - Model and domain logic: `src/core/`
  - View: `src/gui/`
  - Controllers and asynchronous orchestration: `src/controller/`
  - CLI and application bootstrap: `src/commands/`

## Instruction hierarchy

- This file is the repository-wide policy and is authoritative for every change.
- Before changing code under `src`, read `src/CONTEXT.md`, then every
  `CONTEXT.md` on the path to the target package.
- A nearer context refines its parent for local responsibilities, dependencies,
  rules, and validation, but it never overrides this file.
- Tests and non-Python assets inherit the nearest production-package context.
- Detailed architecture and workflow guides remain authoritative where linked by
  a context. When documentation and implementation disagree, inspect tests and
  call sites to establish current behavior and update stale documentation when it
  is in scope.

## Working with this repository

- Inspect relevant files and call sites before editing; use `rg` and `rg --files`
  for discovery.
- Preserve existing conventions and make the smallest coherent change that fully
  addresses the task.
- Treat inventories as discoverable repository state rather than maintaining
  exhaustive lists in instruction files.
- Protect unrelated user changes and avoid destructive Git operations unless the
  user explicitly requests them.
- For every Python coding task, use the `$python-patterns` and `$python-testing`
  skills. They are the source of truth for general Python design and testing.

## Definition of done

Before reporting a code change as complete:

1. Add or update tests for changed behavior; every testable bug fix requires a
   regression test.
2. Run the narrowest relevant checks specified by the owning `CONTEXT.md`.
3. Run `uv run pre-commit run --files <changed files>` with supported changed
   paths listed explicitly.
4. Run `uv run pytest` for shared APIs, configuration, cross-layer behavior, or
   other broad regression risk.
5. For visual GUI changes, run the nearest screenshot test and inspect the
   rendered output. Use a full-window screenshot for shell layout, navigation,
   theme behavior, or changes spanning multiple GUI areas.
6. Regenerate and validate derived files when their sources change.
7. Report exact validation commands and outcomes, including anything skipped or
   unverified and why.

Documentation-only changes require path/link validation and pre-commit; code
tests are required only when the documentation reflects executable behavior that
also changed. Do not describe work as complete while a relevant check is failing.

Tests must be deterministic and must not depend on a real Android device, live
network service, or user-specific state unless the user explicitly authorizes an
integration test.

## Device safety

- Never pair, connect to, disconnect, start or stop spoofing on, or otherwise
  alter a real device unless the user explicitly requests that operation.
- Default development and automated verification to `MockAdb` and the mock launch
  documented in `HOW_TO_mock_adb.md`.
- Never expose pairing codes, credentials, or other sensitive device data.
- Package-specific ADB and device constraints live in
  `src/core/adb/CONTEXT.md` and `src/core/devices/CONTEXT.md`.

## Dependency and generated-file ownership

- `pyproject.toml` is the source of truth for runtime and development
  dependencies. Manage them with `uv add`, `uv add --dev`, `uv remove`, and
  `uv remove --dev`; use `uv lock` and `uv sync --dev` to refresh state.
- Do not edit `uv.lock` manually.
- `requirements.txt` is a generated compatibility export. After dependency
  changes, regenerate it with:

```bash
uv export --all-groups --format requirements-txt --no-hashes --output-file requirements.txt
```

- Package-owned generated files and their rebuild commands are documented by the
  nearest `CONTEXT.md`.

## Git workflow

This repository uses two long-lived branches:

| Branch | Role |
|---|---|
| `dev` | Integration branch for day-to-day development |
| `main` | Stable branch for intentional production releases |

- Branch feature and fix work from an up-to-date `dev` checkout when the user
  requests a branch workflow.
- Open routine pull requests against `dev`, not `main`.
- Do not commit routine work directly to `main`.
- Use `dev...HEAD` for reviews and pull-request summaries.
- Keep branches short-lived and limited to one logical change.

## Documentation index

- Application architecture and launch modes: `README.md`
- GUI design and screenshot workflow: `DESIGN.md`
- Async jobs and result application: `src/HOW_TO_async_jobs.md`
- Controller boundaries and signal flows:
  `src/HOW_TO_controller_and_signals.md`
- Simulation persistence: `src/HOW_TO_simulation_persistence.md`
- Development without real ADB: `HOW_TO_mock_adb.md`
