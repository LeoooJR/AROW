# Close core runtime async flow

Companion to [`close_work.py`](close_work.py). For shared runner and dispatch
conventions, see [`HOW_TO_async_jobs.md`](../../HOW_TO_async_jobs.md).

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

    App->>Controller: enqueue close with after_apply hook
    Controller->>Runner: submit close_core_runtime<br/>thread, latest wins
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
        Controller-->>App: invoke after_apply hook
    else stop or preflight fails
        Work--xRunner: exception in JobError<br/>origin close_core_runtime
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit ERROR_RAISED
        Runner->>Controller: Failed, after apply_failure
        Controller-->>App: invoke after_apply hook
    end
    App->>App: persist simulations, then runner.shutdown()
```

The shutdown event loop is released only by the post-apply handler (or its
watchdog), so runner shutdown cannot normally overtake result/failure application.
