# How controller and GUI signals work

This guide explains how the PySide6 view, GUI signal bus, controllers, and core signal subscriptions fit together in AROW. It matches the current implementation in `src/commands/run/gui.py`, `src/gui/signals.py`, `src/controller/orchestration/app_controller.py`, and the domain subcontrollers under `src/controller/domains/`.

Read this with [`HOW_TO_async_jobs.md`](HOW_TO_async_jobs.md) when you need the lower-level worker-thread and worker-process contract.

## Mental model

AROW separates responsibilities across three layers:

| Layer | Role |
|------|------|
| `gui/` | Emits user intent, owns widgets, and reacts to forwarded state updates. |
| `controller/` | Wires signals, decides which model calls happen, and decides whether work is synchronous or async. |
| `core/` | Owns application state, ADB/runtime logic, persistence, and core-domain signals. |

Two event systems matter:

1. `gui.signals.signals`: view-originating cross-component signals.
2. `core.signals.CoreSignal`: model-originating events emitted after state changes or async result application.

The controller layer is the adapter between them. GUI code should not subscribe directly to `CoreSignal`, and core code should not emit GUI signals.

## Startup sequence

When you run `PYTHONPATH=src python -m main run gui`:

1. `src/commands/run/gui.py` creates `QApplication`.
2. It registers bundled fonts, then creates `MainWindow`.
3. It creates `ModelEntrypoint(use_mock_adb=run_options.mock_adb)`.
4. It creates `AppController(model_entrypoint, view)`.
5. `AppController` constructs subcontrollers in this order:
   - `SimulationSubController`
   - `AdbSubController`
   - `MapSubController`
6. `AppController` connects view signals, connects core signal subscriptions, syncs the activity log file, forwards host metadata, then starts ADB bootstrap via `AdbSubController.run_startup()`.

That initialization order is intentional. Simulation wiring happens before ADB wiring to avoid selection/startup race conditions during early app bootstrap.

## GUI signal categories

`src/gui/signals.py` groups GUI-originating signals into typed categories:

| Category | Examples | Typical consumers |
|------|------|------|
| `signals.UI` | `RenderMapRequested`, `MapTabActivated`, `DisplayLeftPanelsRequested` | controllers and GUI blocks/panels |
| `signals.ADB_SERVER` | `ADBServerStarted`, `ADBServerStopped` | GUI blocks that reflect runtime status |
| `signals.DEVICE` | `AuthentificationConfirmed`, `RefreshDeviceListRequested`, `DeviceSelectionConfirmed` | ADB and simulation controllers |
| `signals.HOST` | `HostDeviceInformationUpdated` | host info cards/panels |
| `signals.ACTIVITY_LOG` | `ActivityLogFileUpdateRequested`, `ActivityLogFileUpdated` | `AppController` and activity log UI |
| `signals.SIMULATION` | `SimulationDeleted`, `SimulationPositionChanged` | map/location UI and related blocks |

Use these categories when adding new GUI-originating events instead of introducing one-off globals.

## Controller responsibilities

### `AppController`

`AppController` is the top-level coordinator.

- Owns the shared `AsyncRunner`.
- Creates and retains the three domain subcontrollers.
- Delegates domain-specific signal wiring to them.
- Handles app-wide concerns that are not specific to one domain, such as host metadata and the current activity log file.
- Coordinates shutdown so startup jobs and close jobs are not abandoned mid-flight.

### Domain subcontrollers

Each domain subcontroller stays narrow:

| Subcontroller | Main responsibilities |
|------|------|
| `AdbSubController` | ADB startup/shutdown, device pairing, device refresh, forwarding ADB/device core events |
| `SimulationSubController` | active simulation lifecycle, device-to-simulation creation, simulation persistence triggers |
| `MapSubController` | render-map requests, cached map reuse, render-job cancellation on simulation deletion |

Subcontrollers do not own separate runners. They delegate async submission through `AppController._submit_model_entrypoint_async_call(...)` so the app has one queueing/cancellation model.

## Main flows

### Device pairing / refresh

1. A view widget emits `signals.DEVICE.AuthentificationConfirmed` or `signals.DEVICE.RefreshDeviceListRequested`.
2. `AdbSubController` receives the signal.
3. It submits the relevant `ModelEntrypoint` call through the shared `AsyncRunner`.
4. Async result application emits the matching `CoreSignal`.
5. `AdbSubController` forwards the result back into the view with methods such as `forward_devices_updated(...)` or `forward_device_authentification_succeeded(...)`.

Constraint: these ADB flows are thread-backed jobs, not process-backed jobs.

### Device selection and simulation creation

1. The view emits `signals.DEVICE.DeviceSelectionConfirmed(device_id, device_name)`.
2. `SimulationSubController._on_device_selection_confirmed(...)` calls `model_entrypoint.create_simulation(...)` on the main thread.
3. The model emits `CoreSignal.SIMULATION_CREATED`.
4. `SimulationSubController._on_simulation_created(...)` forwards `forward_device_selection_succeeded(...)` to the view.

Constraint: simulation creation here is synchronous model orchestration, not an async runner job.

### Map rendering

1. The map block emits `signals.UI.RenderMapRequested(simulation_id)`.
2. `MapSubController` checks whether the simulation already has an existing HTML map file.
3. If the file exists, it forwards the path directly to the view.
4. Otherwise it submits `model_entrypoint.render_map(simulation_id, application_dir)` as `job_type="process"`.
5. When the worker finishes, `CoreSignal.MAP_RENDERED` or `CoreSignal.MAP_RENDER_FAILED` is emitted.
6. `MapSubController` forwards that result to the view.

Constraints:

- Render jobs use `coalesce_key=f"render_map:{simulation_id}"`, so only the latest request per simulation should survive.
- The process-pool target must stay picklable; avoid closing over controller or Qt objects.
- Deleting a simulation cancels any tracked in-flight render job for that simulation.

### Shutdown

`AppController._on_application_about_to_quit()` does more than just stop the runner:

1. Detaches the view reference.
2. Waits for bootstrap jobs (`startup_core_runtime`, `host_install_identity`) to finish, fail, or cancel.
3. Enqueues `close_core_runtime`.
4. Waits for close to apply on the main thread.
5. Persists simulation metadata.
6. Shuts down the shared `AsyncRunner`.

This is why ADB startup and close work should continue to use the controller/runner pipeline instead of bespoke threads or direct shutdown calls.

## Adding a new controller-driven flow

Use this checklist when introducing a new user action:

1. Add a typed GUI-originating signal to the right category in `src/gui/signals.py` if the flow starts from the view.
2. Connect it in the relevant `connect_view_signals()` method.
3. Keep widget logic in `gui/`, orchestration in `controller/`, and state mutation in `core/`.
4. If the work blocks on I/O or CPU, route it through `_submit_model_entrypoint_async_call(...)`.
5. Emit or reuse a `CoreSignal` for model-side outcomes.
6. Subscribe in the relevant `connect_model_signals()` method and forward the result to the view.
7. Add targeted tests where the flow is owned:
   - controller tests for orchestration
   - GUI/block tests for signal emission and forwarded behavior

## Common pitfalls

- Do not emit core-domain events through `gui.signals`; keep the controller as the boundary adapter.
- Any custom slot connected with `.connect(...)` or `QTimer.singleShot(...)` should use `@Slot(...)` with an appropriate signature.
- Do not add ad-hoc threads for model work. Use the shared `AsyncRunner` so cancellation, coalescing, and shutdown behavior stay consistent.
- For map rendering, preserve the cached-HTML fast path before adding heavier invalidation or refresh logic.
