# How simulation persistence works

This guide describes how AROW persists simulation metadata to disk, when that metadata is refreshed, how startup restores it, and which recovery rules intentionally delete stale state.

It matches the implementation in `src/core/simulation.py`, `src/core/entrypoint.py`, `src/core/work/startup_work.py`, `src/controller/domains/simulation_sub_controller.py`, and `src/controller/domains/map_sub_controller.py`.

## Mental model

- `SimulationRepository` is the in-memory collection used by `ModelEntrypoint`.
- `SimulationDiskStore` owns the JSON files and simulation directories under the app data directory.
- Controllers do not write JSON directly. They update model state or respond to core signals, and the model/repository persists the resulting simulation metadata.
- Startup is conservative: it restores only simulations that can still be bound to a currently paired device.

## On-disk layout

Simulation data lives under:

```text
<application_dir>/simulations/
  index.json
  <simulation_id>/
    simulation.json
    <simulation_id>.log
    map/
      <simulation_id>.html
```

Key files:

- `index.json`: ordered list of known simulation ids plus `last_active_device_id`.
- `<simulation_id>/simulation.json`: persisted metadata for one simulation.
- `<simulation_id>/<simulation_id>.log`: per-simulation log file created when the simulation is first added.
- `<simulation_id>/map/<simulation_id>.html`: rendered Folium map cache when map generation succeeds.

`simulation.json` currently uses schema version `1` and stores:

- `id`
- `device`
- `real_location`
- `fake_location`
- `map_file`
- `log_file`
- `active`

Artifact paths are stored relative to the simulation directory when possible. If a path points outside that directory, it is stored as an absolute path instead.

## When data is written

### On simulation creation

`ModelEntrypoint.create_simulation(device_id)` creates a new `Simulation` only if that device does not already have one.

On first creation, `SimulationRepository.add(...)` immediately:

1. Creates the simulation directory.
2. Creates the default per-simulation log file.
3. Writes `simulation.json`.
4. Rewrites `index.json`.

If the same device is selected again later, the existing simulation is reused rather than duplicated. The selected device id is still written back to `index.json` as `last_active_device_id`.

### On state, location, and map changes

Simulation metadata is refreshed incrementally rather than only at shutdown.

`SimulationSubController` subscribes to:

- `SIMULATION_STATE_CHANGED`
- `SIMULATION_POSITION_CHANGED`
- `SIMULATION_MAP_FILE_CHANGED`
- `MAP_RENDERED`

For each of those signals it calls `ModelEntrypoint.persist_simulation(simulation_id)`, which rewrites only that simulation's `simulation.json`.

This means the persisted JSON follows runtime changes for:

- `active`
- `real_location`
- `fake_location`
- `map_file`

### On bulk persistence

`ModelEntrypoint.persist_simulations()` rewrites every simulation metadata file and then rewrites `index.json`. `MapSubController.persist_simulation_repository()` uses this path for shutdown-oriented persistence.

JSON writes are atomic: files are written through a `*.tmp` sibling and then replaced in place.

## Startup restore flow

`StartupCoreRuntimeWork.run()` loads persisted simulations from:

```python
SimulationDiskStore(get_or_create_application_dir() / "simulations")
```

The worker returns:

- current paired devices from ADB
- restored simulations that still match those paired devices
- `last_active_device_id`

`StartupCoreRuntimeWork.apply_main_thread(...)` then:

1. Restores each loaded simulation into the in-memory repository.
2. Emits `ADB_SERVER_STARTED` and `DEVICES_UPDATED`.
3. Syncs `last_active_device_id` into the repository.
4. Replays `create_simulation(last_active_device_id)` when that device is still paired and in `device` state.

That final step is intentional. Startup does not just remember which device was active; it reuses the normal simulation-selection pathway so downstream state and signals stay consistent.

## Device matching and recovery rules

Restore is not a blind JSON load. `SimulationDiskStore.load_for_devices(...)` applies strict binding rules against the current paired-device repository.

### Normal restore

If `simulation.device.id` is still present in the paired device repository, the restored simulation is rebound to that existing in-memory `Phone` instance.

This preserves object identity across the model: the simulation points at the same `Phone` object the rest of the runtime uses.

### Rebind on ADB id change

Wireless reconnects can change a device's ADB connection id. When that happens, AROW may still restore the simulation by matching the persisted device's `stable_key`.

This only happens when `phone_stable_key_is_collision_resistant(stable_key)` returns true. Tier-2 fingerprints are intentionally not trusted for destructive rebinding.

If a persisted simulation is rebound this way, `last_active_device_id` is updated to the new paired device id before `index.json` is rewritten.

### Delete stale or invalid state

AROW deletes a persisted simulation directory during restore when any of these are true:

- `simulation.json` is missing.
- `simulation.json` cannot be parsed as JSON.
- The payload schema version is unsupported.
- The payload is structurally invalid.
- The persisted simulation has no device.
- No currently paired device matches by id or collision-resistant stable key.

After cleanup, `index.json` is rewritten so only successfully restored simulations remain.

If `last_active_device_id` no longer points to a currently paired device after restore, it is cleared and persisted as `null`.

## Runtime reconcile behavior after startup

`ModelEntrypoint.reconcile_paired_devices(...)` handles later ADB refreshes after startup.

Important consequences:

- Newly discovered devices are added to the paired-device repository.
- Existing devices are updated in place when they match by ADB id or collision-resistant stable key.
- Simulations keep pointing at the same `Phone` object when the device is updated in place.
- Devices missing from the refreshed discovery list are removed.
- Any simulation bound to a removed device is deleted best-effort.

This is separate from startup restore, but together these two flows explain why a simulation can survive a reconnect yet still be deleted when its device is genuinely gone.

## Map rendering and cache reuse

Map HTML is rendered by `RenderMapWork` into:

```text
<application_dir>/simulations/<simulation_id>/map/<simulation_id>.html
```

`RenderMapWork.apply_main_thread(...)` sets `simulation.map_file` and emits `MAP_RENDERED`. `SimulationSubController` hears that signal and persists the updated `map_file` back into `simulation.json`.

Later, when the UI requests the same map again, `MapSubController._on_render_map_requested(...)` checks `simulation.map_file` first:

- if the HTML file still exists, it forwards that cached path directly to the view
- otherwise it submits a new process-backed render job

If rendering fails with `RenderMapError`, the main-thread failure path clears `simulation.map_file` and emits `MAP_RENDER_FAILED`.

## Constraints and pitfalls

- Keep ADB-facing logic out of persistence code. Device discovery and reconciliation belong in `ModelEntrypoint` and ADB work modules.
- Keep persistence path handling on `pathlib.Path`; simulation payloads can legitimately contain either relative or absolute artifact paths.
- Do not assume every persisted simulation survives restart. Missing devices and invalid metadata are intentionally cleaned up.
- When adding new persisted fields, update both `Simulation.to_payload(...)` and `Simulation.from_payload(...)`, and add restore/write coverage in `src/core/tests/test_simulation_repository_persistence.py`.
- When changing reconcile rules, also update `src/core/tests/test_entrypoint_reconcile.py` because restore and runtime refresh must keep the same device-identity guarantees.

## Useful tests

- `src/core/tests/test_simulation_repository_persistence.py`
- `src/core/tests/test_entrypoint_reconcile.py`
- `src/controller/domains/tests/test_simulation_sub_controller.py`
- `src/controller/domains/tests/test_map_sub_controller.py`
