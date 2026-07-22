# AROW Project Instructions

## Project overview

- AROW is a PySide6 desktop application that spoofs an Android phone's coordinates through Android Debug Bridge (`ADB`).
- Bundled platform tools live in `src/assets`; ADB integration lives in `src/core/adb/`.
- The project follows an MVC split:
  - Model and domain logic: `src/core/`
  - View: `src/gui/`
  - Controllers and async orchestration: `src/controller/`
- Geo datasets, validation, and Folium rendering live in `src/core/geo/`.

## Working with this repository

- Inspect relevant files and call sites before editing; use `rg` and `rg --files` to discover the current structure.
- Preserve existing conventions and make the smallest coherent change that fully addresses the task.
- Treat changing package, component, block, settings, and test inventories as discoverable repository state. Do not rely on or add exhaustive inventories to this file.
- For every Python coding task, use the `$python-patterns` and `$python-testing` skills. They are the source of truth for general Python design and testing practices; this file contains only AROW-specific constraints.

## Definition of done

Before reporting a code change as complete:

1. Add or update tests for changed behavior; every bug fix requires a regression test when the behavior is testable.
2. Run the narrowest relevant tests first, following the test-selection matrix below.
3. Run `uv run pre-commit run --files <changed files>` for supported changed files, listing the paths explicitly in the command.
4. Run the full suite with `uv run pytest` when the change crosses architectural boundaries, affects shared APIs or configuration, or otherwise has broad regression risk.
5. For visual GUI changes, run the relevant screenshot test and inspect the rendered output; use a full-window screenshot when shell layout, navigation, theme behavior, or multiple GUI areas change.
6. Regenerate and validate derived files when their sources change.
7. Report the exact validation commands and outcomes, including any skipped or unverified checks and why they were not run.

Do not describe work as complete while a relevant check is failing.

## Test selection

Use the narrowest applicable row first. Expand validation when a change affects more than one area.

| Changed area | Minimum validation |
|---|---|
| `src/core/adb/` or `src/core/devices/` | Corresponding ADB or device tests discovered under `src/` plus affected `src/core/work/` or controller tests; use mocks only |
| `src/core/geo/` or map rendering | Relevant `src/core/geo/tests/` tests plus affected render-map work and map-controller tests |
| `src/core/work/` or model entrypoint behavior | Targeted work tests plus affected `src/core/tests/` and domain-controller tests |
| `src/controller/` or async lifecycle | Targeted controller tests; cover success, failure, cancellation, cleanup, and stale-result behavior when applicable |
| GUI component or block behavior | The nearest behavioral tests under the owning component, block, or `src/gui/tests/` |
| GUI appearance, layout, icons, or theme | Behavioral tests plus the nearest `@pytest.mark.screenshot` test and visual inspection, following `DESIGN.md` |
| Signals or application lifecycle | Relevant controller tests plus main-window or integration tests |
| Shared API, dependency, test configuration, or cross-layer change | Targeted tests followed by `uv run pytest` |
| Documentation only | Validate referenced paths and commands; run code tests only when the documentation reflects executable behavior that changed |

Tests must be deterministic and must not depend on a real Android device, live network service, or user-specific state unless the user explicitly authorizes an integration test.

## ADB and device safety

- Default to `MockAdb`, test fixtures, and `PYTHONPATH=src python -m main run --mock-adb gui` for development and verification.
- Never pair, connect to, disconnect, start or stop spoofing on, or otherwise alter a real device unless the user explicitly requests that operation.
- Do not use a real connected device as an incidental test target. Mock subprocess and ADB boundaries in automated tests.
- Never expose or log pairing codes, credentials, or other sensitive device data. Preserve the project's logging-redaction behavior.
- Keep all ADB subprocess and protocol calls inside `src/core/adb/`; GUI and controller code must communicate through model APIs rather than invoking ADB directly.

## Documentation routing

Read the relevant source before changing these areas:

| Area | Authoritative guide |
|---|---|
| Application architecture and launch modes | `README.md` |
| GUI appearance, spacing, themes, and screenshot workflow | `DESIGN.md` |
| Async jobs, work application, cancellation, and worker logging | `src/HOW_TO_async_jobs.md` |
| Controller boundaries and GUI/core signal flows | `src/HOW_TO_controller_and_signals.md` |
| Simulation persistence and stale-state cleanup | `src/HOW_TO_simulation_persistence.md` |
| Development without a real ADB installation | `HOW_TO_mock_adb.md` |

When implementation and documentation disagree, inspect tests and call sites to establish current behavior, then update stale documentation as part of the same change when it is in scope.

## Dependency and generated-file ownership

- `pyproject.toml` is the source of truth for runtime and development dependencies.
- Manage dependencies with uv so `pyproject.toml` and `uv.lock` stay synchronized:
  - Runtime dependency: `uv add <package>`
  - Development dependency: `uv add --dev <package>`
  - Remove a dependency: `uv remove <package>` or `uv remove --dev <package>`
  - Refresh the lockfile: `uv lock`
  - Synchronize the development environment: `uv sync --dev`
- Do not edit `uv.lock` manually.
- `requirements.txt` is a generated compatibility export, not a dependency source. After dependency changes, regenerate it with:

```bash
uv export --all-groups --format requirements-txt --no-hashes --output-file requirements.txt
```

- `src/gui/ressources_rc.py` is generated from `src/gui/ressources.qrc`; never edit it manually. Rebuild it after changing referenced GUI assets or the resource manifest:

```bash
uv run pyside6-rcc src/gui/ressources.qrc -o src/gui/ressources_rc.py
```

## Git workflow

This repository uses two long-lived branches:

| Branch | Role |
|---|---|
| `dev` | Integration branch for day-to-day development |
| `main` | Stable branch for intentional production releases |

- Branch feature and fix work from an up-to-date `dev` checkout when the user requests a branch workflow.
- Open routine pull requests against `dev`, not `main`.
- Do not commit routine work directly to `main`.
- Use `dev...HEAD` for reviews and pull-request summaries.
- Keep branches short-lived and limited to one logical change.

## Architecture boundaries

- Keep network logic in `src/core/network.py`.
- Keep device behavior, metadata, repositories, and related dataclasses in `src/core/devices/`.
- Keep model work out of GUI and controller modules.
- Keep controllers focused on translating view intent, submitting model work, and routing model results back to the view.

## Geo and dataset standards

Apply these rules whenever changing `src/core/geo/`.

### Tabular and spatial data operations

- Treat `pandas.DataFrame`, `geopandas.GeoDataFrame`, and related structures as columnar data.
- Prefer vectorized APIs, joins, concatenation, groupby aggregations, and spatial joins over row-wise Python loops.
- Avoid `iterrows`, per-row `apply` with Python callables, and manual index loops unless no practical vectorized alternative exists.
- If a scalar loop is required for a third-party API, isolate it, explain why, and keep the hot path small.

### Dataset validation

- Express dataset shape, dtype, column, and value constraints with `pandera`.
- Validate data at clear boundaries such as after load, before export, or before handing data to the map pipeline.
- Reuse or extend schemas in `src/core/geo/datasets.py`, `src/core/geo/dataset_schemas.py`, or a nearby schema module instead of scattering ad-hoc checks.
- Translate schema failures into explicit project exceptions following `src/core/geo/exceptions.py` and the `SchemaValidationError` pattern.

### Map rendering

- Build server-side map HTML with `folium`; do not replace the map stack with ad-hoc Leaflet string generation without an explicit migration decision.
- Keep first paint fast by preparing data in Python, simplifying display geometry when appropriate, and limiting redundant layers and inline assets.
- Keep `pandera` and `folium` declared in `pyproject.toml` when extending schema or map features.

## Async model work

- Route model-side heavy work, map creation, and I/O through `src/controller/runner.py`.
- Use `JobSpecification` and `AsyncRunner.submit(job)`.
- Use the returned `JobHandler` and `runner.bind_handle_signals(handle)` when per-job signals are needed.
- Wire core-runtime completion and failure to `ModelEntrypoint.apply_result` and `ModelEntrypoint.apply_failure`, which dispatch to registered work appliers.
- Keep post-apply chaining, shutdown hooks, cancellation, and job-tracking cleanup as focused lifecycle handlers in the owning domain subcontroller.
- Do not introduce ad-hoc threads or processes for model work.

## Qt model/view usage

- Prefer Qt model classes in `src/core/qt_models.py` when the view needs lists, tables, or trees.
- Use Qt model/view instead of passing plain Python collections through the controller when it provides the cleaner ownership boundary.

## GUI standards

Apply these rules whenever changing `src/gui/`. Discover current categories and owner-local modules with `rg --files src/gui` instead of maintaining their inventory here.

### Design, settings, and colors

- Treat `DESIGN.md` as the source of truth for visual direction and screenshot verification.
- Use `Settings` from `src/gui/settings.py` only for cross-cutting layout tokens shared by multiple owners.
- Put owner-specific sizing and timing constants in a frozen `<owner>_settings.py` dataclass module next to the component, block, or panel.
- Use colors from `src/gui/colors.py`; add reusable colors there instead of defining one-off values.
- Keep styling in `src/gui/stylesheet.py`; do not embed inline style strings in other Python modules.

### Components, blocks, and panels

- Put reusable GUI components under the best-fitting category in `src/gui/components/`; create a category when no existing one fits.
- Treat `src/gui/elements.py` as a backward-compatible re-export shim only. New code imports from `gui.components` or the owning category.
- Export reusable components from the owning category and `src/gui/components/__init__.py` when they are intended for project-wide use.
- Components participating in the shared lifecycle inherit from `Component`, implement the lifecycle hooks, and call `_finalize_ui_hooks()` after child widgets and state are initialized.
- Put reusable multi-component widgets in `src/gui/blocks/`, preferably one block per file, and keep owner-specific helpers beside their block.
- Export reusable blocks from the owning category and `src/gui/blocks/__init__.py` when intended for project-wide use.
- Blocks participating in the shared lifecycle inherit from `Block`, implement the lifecycle hooks, and call `_finalize_ui_hooks()` after initialization.
- Prefer owner-local `Text` and `UI` dataclasses for stable copy and meaningful child-widget references.
- Blocks own block-specific rendering, filtering, selection, placeholders, theme propagation, and signal handlers.
- Panels remain thin shells for chrome, visibility, orchestration, data routing, and explicit public facade methods. Do not reach through chained block internals from outside the owner.
- Put block-internal tests in the owning block category's `tests/`; keep panel, window, component integration, and end-to-end GUI tests in `src/gui/tests/`.
- Use layout helpers from `src/gui/wrapper.py` when they fit.

### Icons and resources

- Use `src/gui/icons.py` for Qt resource icons.
- Use `src/core/geo/icons.py` for Folium or Leaflet map icons.
- Keep assets under `src/gui/statics/` synchronized with `src/gui/ressources.qrc`, then regenerate the compiled resource module as described above.

### Signals and slots

- Use view-originating signals from the categorized singleton in `src/gui/signals.py`: `from gui.signals import signals`.
- Add new GUI-originating signals to the appropriate category on `signals`; do not use or extend the legacy flat `view_signals` or `ViewSignals` API.
- Sidebar visibility uses explicit `Display*` and `Hide*` signals; do not reintroduce boolean left/right toggle signals.
- Decorate every custom method connected with `.connect(...)` or `QTimer.singleShot(...)` using a typed `@Slot(...)` signature aligned with the signal contract.
- Use named handler methods instead of lambda slot targets.
- Do not decorate direct `.emit` bridges or Qt built-in methods.
- Apply the same slot rule to controller handlers wired in `connect_view_signals()` and `AppController._connect_view_signals()`.
- Do not decorate `model_entrypoint.subscribe(...)` handlers; they use the core bus, not Qt. Controllers remain plain Python classes.

### Animations

- Implement common animation helpers in `src/gui/animation.py` and reuse them instead of duplicating animation logic in widgets or panels.
