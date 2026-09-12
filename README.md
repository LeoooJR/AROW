# AROW

<p align="center">
  <img src="logo.png" alt="AROW logo" width="220">
</p>

**Advanced Railway geOlocation Workflow** is a PySide6 desktop application for
railway research and development. It combines railway-specific geographic data
with controlled Android GPS simulation: explore railways, stations, and
milestones, then send a selected location to a companion phone through Android
Debug Bridge (ADB).

## Features

- Explore railway infrastructure on Folium-based interactive maps.
- Query bundled railway and milestone referentials from the command line.
- Simulate Android GPS coordinates through ADB-managed workflows.
- Develop and demonstrate the complete desktop flow safely with a seedable,
  faker-backed mock ADB implementation.
- Capture human-readable or structured JSON Lines logs across the application
  and map-rendering workers.

## Requirements

- Python 3.12 or later
- [`uv`](https://docs.astral.sh/uv/) for dependency and environment management
- A graphical desktop environment for the PySide6 interface

A real Android device is not required for development. The recommended first
run uses mock ADB and does not start an ADB daemon or interact with a phone.

## Installation

Clone the repository, enter its root directory, and install the application and
development dependencies:

```bash
git clone git@github.com:LeoooJR/AROW.git
cd AROW
uv sync --dev
```

## Quick start

Launch the complete desktop application with mock ADB:

```bash
PYTHONPATH=src uv run python -m main run --mock-adb gui
```

Mock mode provides synthetic device discovery, pairing, and ADB responses. For
repeatable mock-device data, set `AROW_MOCK_ADB_SEED` to an integer before
launching. See [How to run AROW with mock ADB](docs/HOW_TO_mock_adb.md) for the
full behavior and troubleshooting guide.

## Command-line workflows

Run `PYTHONPATH=src uv run python -m main --help` to inspect the command tree.

### Launch the desktop application

Running without `--mock-adb` uses the real ADB-backed workflow and may interact
with configured Android devices:

```bash
PYTHONPATH=src uv run python -m main run gui
```

### Write structured logs to a chosen directory

```bash
PYTHONPATH=src uv run python -m main run \
  --mock-adb \
  --json-logs \
  --log-dir ./arow-logs \
  gui
```

The main application writes to a UUID4-named log file. Process-backed workers
write `<run_identifier>.worker-<pid>.log` siblings in the same directory. Read
every file sharing the run identifier to reconstruct a complete trace.

### Query a milestone

Provide a six-digit railway code, section number, and positive integer kilometer
code:

```bash
PYTHONPATH=src uv run python -m main query milestone 001000 1 1
```

When the milestone exists, AROW displays its canonical primary-key label,
coordinates, railway metadata, and a QR code.

### Query a railway

Provide the railway's six-digit line code and positive section number:

```bash
PYTHONPATH=src uv run python -m main query railway 001000 1
```

When the railway exists, AROW displays its metadata and a QR code encoding the
composite key, such as `001000-1`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `AROW_USE_MOCK_ADB` | Enable mock ADB when set to `1`, `true`, or `yes` (case-insensitive). |
| `AROW_MOCK_ADB_SEED` | Use an integer seed for repeatable mock-device data. |
| `AROW_LOG_FALLBACK_DIR` | Choose a fallback when the default log directory is not writable. |

The equivalent command-line options are available under
`PYTHONPATH=src uv run python -m main run --help`. An explicit `--log-dir` must
be writable; AROW reports a startup error instead of redirecting it to the
fallback directory.

## Architecture

AROW follows a model-view-controller split:

- `src/core/` owns domain logic, ADB/runtime work, persistence, and map
  generation. Its `geo` package owns railway datasets, validation, and
  Folium-based rendering.
- `src/gui/` owns the PySide6 view layer, reusable components, pages, panels,
  and GUI signals.
- `src/controller/` translates GUI intents into model work and applies model
  events to the view.
- `src/commands/` composes the CLI and application bootstrap.

The GUI bootstrap creates `MainWindow`, `ModelEntrypoint`, `AppController`, and
the simulation, ADB, and map subcontrollers. `AppController` owns the shared
`AsyncRunner`; blocking ADB and map jobs flow through it instead of ad hoc
threads.

## Contributing

Install the development dependencies with `uv sync --dev`, then run the test
suite and repository checks:

```bash
uv run pytest
uv run pre-commit run --all-files
```

Before changing production code, follow the repository's context hierarchy:

1. Read [`AGENTS.md`](AGENTS.md) for repository-wide policy.
2. Read [`src/CONTEXT.md`](src/CONTEXT.md) for application-layer boundaries.
3. Continue through each `CONTEXT.md` on the path to the package being changed.

The nearest context describes package responsibilities, dependencies, and
validation. Tests and non-Python assets inherit the nearest production-package
context.

## Developer guides

- [Agent-oriented design workflow](docs/HOW_TO_agent_design_workflow.md)
- [Asynchronous jobs and process-backed map rendering](docs/HOW_TO_async_jobs.md)
- [Controllers, signals, and user-driven flows](docs/HOW_TO_controller_and_signals.md)
- [Simulation persistence](docs/HOW_TO_simulation_persistence.md)
- [Desktop and mobile communication](docs/HOW_TO_mobile_communication.md)
- [Mock ADB development](docs/HOW_TO_mock_adb.md)
- [GUI design and screenshot workflow](DESIGN.md)

## License

AROW is licensed under the [GNU Affero General Public License v3.0](LICENSE.md).
