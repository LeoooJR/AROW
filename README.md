# AROW
Advanced Railway geolocatiOn Workflow

## Architecture at a glance

AROW is a desktop app that spoofs a phone's location over ADB.

- `src/gui/`: PySide6 view layer, reusable components, blocks, panels, and cross-GUI signals.
- `src/controller/`: orchestration layer that translates GUI intents into model work and forwards model events back to the view.
- `src/core/`: model, ADB/runtime work, persistence, and map-generation entrypoints.
- `src/core/geo/`: geo datasets, validation, and Folium-based map rendering.

The main CLI entrypoint is `PYTHONPATH=src python -m main`. Starting without `--interface-only` creates:

1. `MainWindow`
2. `ModelEntrypoint`
3. `AppController`
4. three domain subcontrollers: simulation, ADB, and map

`AppController` owns the shared `AsyncRunner`; blocking ADB and map jobs should go through it instead of ad-hoc threads.

## Developer docs

- [`src/HOW_TO_async_jobs.md`](src/HOW_TO_async_jobs.md) explains the async `CoreRuntimeWork` flow, result/failure dispatch, process-backed map rendering, and shared worker logging.
- [`src/HOW_TO_controller_and_signals.md`](src/HOW_TO_controller_and_signals.md) explains the GUI signal categories, controller/subcontroller responsibilities, startup/shutdown orchestration, and the main user-driven flows.
- [`HOW_TO_mock_adb.md`](HOW_TO_mock_adb.md) explains how to run the app without a real ADB installation.

## Common developer workflows

### Run the full app

```bash
PYTHONPATH=src python -m main
```

### Run without real ADB

```bash
PYTHONPATH=src python -m main --mock-adb
```

### Run interface only

```bash
PYTHONPATH=src python -m main --interface-only
```

`--interface-only` starts the Qt UI without constructing `ModelEntrypoint` or `AppController`, so async core jobs, ADB, and mock ADB are all bypassed.
