# Host install identity async flow

Companion to [`host_install_identity_work.py`](host_install_identity_work.py).
For shared runner and dispatch conventions, see
[`HOW_TO_async_jobs.md`](../../HOW_TO_async_jobs.md).

**Job:** `host_install_identity` | **Pool:** thread | **Coalesce key:**
`host_install_identity`

```mermaid
sequenceDiagram
    autonumber
    participant Controller as AdbSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as HostInstallIdentityWork
    participant Disk as install_identity file
    participant Host as Host model
    participant Bus as Core signal bus

    Controller->>Runner: submit after startup apply<br/>thread, latest wins
    Runner->>Entrypoint: run_host_install_identity() in worker thread
    Entrypoint->>Work: construct and run()
    Work->>Disk: read existing token
    alt token is absent or blank
        Work->>Disk: exclusive-create UUID token
        opt another process wins create race
            Work->>Disk: read winning token
        end
    end
    alt worker succeeds
        Work-->>Runner: HostInstallIdentityOutcome(token)
        Runner->>Entrypoint: apply_result(outcome) on main thread
        Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
        alt token is non-empty
            Work->>Work: derive computer stable key
            Work->>Host: set_host_identity(stable_key)
            Host->>Bus: emit HOST_COMPUTER_IDENTITY_UPDATED
        else token is empty
            Work->>Work: log warning and leave identity unchanged
        end
    else disk or create-race failure
        Work--xRunner: exception in JobError<br/>origin host_install_identity
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit ERROR_RAISED
    end
```
