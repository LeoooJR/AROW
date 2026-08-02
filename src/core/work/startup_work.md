# Startup core runtime async flow

Companion to [`startup_work.py`](startup_work.py). For shared runner and dispatch
conventions, see [`HOW_TO_async_jobs.md`](../../../docs/HOW_TO_async_jobs.md).

**Job:** `startup_core_runtime` | **Pool:** thread | **Coalesce key:** `startup`

```mermaid
sequenceDiagram
    autonumber
    participant App as AppController
    participant Controller as AdbSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as StartupCoreRuntimeWork
    participant Bus as Core signal bus

    App->>Controller: run_startup()
    Controller->>Runner: submit startup_core_runtime<br/>thread, coalesce startup
    Runner->>Entrypoint: startup() in worker thread
    Entrypoint->>Entrypoint: resolve effective ADB mode and binary path
    Entrypoint->>Work: construct(use_mock_adb, adb_binary_path, simulations_dir) and run()
    Work->>Work: start real or mock ADB server/client
    Work->>Work: enrich paired devices and load simulations
    alt worker succeeds
        Work-->>Entrypoint: StartupOutcome
        Entrypoint-->>Runner: StartupOutcome
        Runner->>Entrypoint: apply_result(outcome) on main thread
        Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
        Work->>Entrypoint: assign ADB server/client and restore simulations
        Work->>Bus: emit ADB_SERVER_STARTED and DEVICES_UPDATED
        Work->>Entrypoint: sync last active device and restore simulation selection
        Runner->>Controller: Completed(outcome), after apply_result
        Controller->>Controller: enqueue host_install_identity
    else worker raises
        Work--xRunner: exception wrapped as JobError<br/>origin startup_core_runtime
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit ERROR_RAISED
    end
```

The host identity submission is connected after `apply_result`, so it cannot run
until startup state and signals have been applied.
