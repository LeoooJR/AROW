# Close core runtime async flow

Companion to [`close_work.py`](close_work.py). For shared runner and dispatch
conventions, see [`HOW_TO_async_jobs.md`](../../../docs/HOW_TO_async_jobs.md).

**Job:** `close_core_runtime` | **Pool:** thread | **Coalesce key:** `close`

```mermaid
sequenceDiagram
    autonumber
    participant App as AppController shutdown
    participant Controller as AdbSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as CloseCoreRuntimeWork
    participant Bus as Core signal bus

    App->>Controller: run_shutdown()
    Controller->>Runner: submit close_core_runtime<br/>thread, latest wins
    App->>Runner: request_drain(timeout)
    Runner->>Entrypoint: close_core_runtime() in worker thread
    alt no active ADB server
        Entrypoint-->>Runner: CloseOutcome(adb_server=None)
    else server exists
        Entrypoint->>Work: construct(server) and run()
        Work->>Work: preflight running server, then stop it
        Work-->>Runner: CloseOutcome(stopped server)
    end
    alt worker succeeds
        Runner->>Entrypoint: apply_result(outcome) on main thread
        Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
        alt stopped server is present
            Work->>Entrypoint: clear ADB server and client
            Work->>Bus: emit ADB_SERVER_STOPPED
        else no-op outcome
            Work->>Work: log warning and keep state unchanged
        end
        Runner->>Controller: Completed, after apply_result
    else stop or preflight fails
        Work--xRunner: exception in JobError<br/>origin close_core_runtime
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit ERROR_RAISED
        Runner->>Controller: Failed, after apply_failure
    end
    Runner-->>App: Drained after terminal listeners
    App->>App: persist simulations, then runner.shutdown()
```

The runner evaluates drains after runner-level and handle-level terminal
listeners. The entrypoint result or failure applier therefore completes before
`Drained` advances application teardown. No nested Qt event loop or controller
callback hook is involved. If the close deadline expires, the application stays
alive and an unbounded drain continues observing the already-started close.
