# AROW
Advanced Railway geolocatiOn Workflow

## Architecture at a glance

AROW is a desktop app that spoofs a phone's location over ADB.

- `src/gui/`: PySide6 view layer, reusable components, blocks, panels, and cross-GUI signals.
- `src/controller/`: orchestration layer that translates GUI intents into model work and forwards model events back to the view.
- `src/core/`: model, ADB/runtime work, persistence, and map-generation entrypoints.
- `src/core/geo/`: geo datasets, validation, and Folium-based map rendering.

The main GUI entrypoint is `PYTHONPATH=src python -m main run gui`. The GUI command creates:

1. `MainWindow`
2. `ModelEntrypoint`
3. `AppController`
4. three domain subcontrollers: simulation, ADB, and map

`AppController` owns the shared `AsyncRunner`; blocking ADB and map jobs should go through it instead of ad-hoc threads.

## Developer docs

- [`docs/HOW_TO_agent_design_workflow.md`](docs/HOW_TO_agent_design_workflow.md) explains the agent-oriented design workflow.
- [`docs/HOW_TO_async_jobs.md`](docs/HOW_TO_async_jobs.md) explains the async `CoreRuntimeWork` flow, result/failure dispatch, process-backed map rendering, and process-safe worker logging.
- [`docs/HOW_TO_controller_and_signals.md`](docs/HOW_TO_controller_and_signals.md) explains the GUI signal categories, controller/subcontroller responsibilities, startup/shutdown orchestration, and the main user-driven flows.
- [`docs/HOW_TO_simulation_persistence.md`](docs/HOW_TO_simulation_persistence.md) explains where simulation metadata lives on disk, when it is persisted, how startup restores it, and when stale state is deleted.
- [`docs/HOW_TO_mobile_communication.md`](docs/HOW_TO_mobile_communication.md) describes the desktop-to-mobile communication contract.
- [`docs/HOW_TO_mock_adb.md`](docs/HOW_TO_mock_adb.md) explains how to run the app without a real ADB installation.

## Module context

Every production Python package has a `CONTEXT.md` describing its purpose,
architectural boundaries, local rules, primary dependencies, and validation.
These files form a hierarchy rather than standalone copies of the same guidance:

1. Read [`AGENTS.md`](AGENTS.md) for repository-wide policy.
2. Read [`src/CONTEXT.md`](src/CONTEXT.md) for application-layer boundaries.
3. Continue through each `CONTEXT.md` on the path to the package being changed.

The nearest context supplies the most specific guidance but never overrides
`AGENTS.md`. Tests and non-Python assets inherit the nearest production-package
context. The detailed HOW-TO documents above remain authoritative and are linked
from the contexts that use them.

## Common developer workflows

### Run the full app

```bash
PYTHONPATH=src python -m main run gui
```

### Run without real ADB

```bash
PYTHONPATH=src python -m main run --mock-adb gui
```

### Run with machine-readable logs

```bash
PYTHONPATH=src python -m main run --json-logs --mock-adb gui
```

This writes one JSON object per line to the UUID4-named main application log and
PID-specific `<run_identifier>.worker-<pid>.log` siblings. Analyze every file
with the same run identifier prefix for a complete trace. Each record includes
Loguru's timestamp, level, source, process, thread, exception, and structured
`extra` fields, plus AROW's normalized `origin` and `log_schema_version` fields.

### Write logs to an agent-readable directory

```bash
PYTHONPATH=src python -m main run --log-dir ./arow-logs --json-logs --mock-adb gui
```

`--log-dir` accepts an absolute, relative, or `~`-based directory and creates it
when needed. The main log keeps its UUID4 filename and worker logs remain beside
it. An explicitly requested directory must be writable; startup fails clearly
instead of silently redirecting those logs to the temporary fallback directory.
