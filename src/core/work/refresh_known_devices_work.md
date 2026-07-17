# Refresh known devices async flow

Companion to [`refresh_known_devices_work.py`](refresh_known_devices_work.py).
For shared runner and dispatch conventions, see
[`HOW_TO_async_jobs.md`](../../HOW_TO_async_jobs.md).

**Job:** `refresh_device_list` | **Pool:** thread | **Coalesce key:**
`refresh_device_list` | **Policy:** at most once

```mermaid
sequenceDiagram
    autonumber
    participant Source as UI or 30-second timer
    participant Controller as AdbSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as RefreshKnownDevicesWork
    participant Bus as Core signal bus
    participant View

    Source->>Controller: RefreshDeviceListRequested
    Controller->>Runner: submit refresh_device_list<br/>thread, at_most_once
    alt same coalesce key is active
        Runner-->>Controller: no handle, request skipped
    else submission accepted
        Runner->>Entrypoint: refresh_known_devices() in worker thread
        Entrypoint->>Work: construct(ADB runtime) and run()
        Work->>Work: preflight server and client
        Work->>Work: list devices and enrich targetable phones
        alt worker succeeds
            Work-->>Runner: RefreshKnownDevicesOutcome(devices)
            Runner->>Entrypoint: apply_result(outcome) on main thread
            Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
            Work->>Entrypoint: reconcile_paired_devices(devices)
            alt repository changed
                Work->>Bus: emit DEVICES_UPDATED
                Bus-->>Controller: devices and ID rebindings
                Controller-->>View: forward devices update
            else no effective change
                Work->>Work: return without emitting
            end
        else listing or preflight fails
            Work--xRunner: exception in JobError<br/>origin refresh_device_list
            Runner->>Entrypoint: apply_failure(job_error) on main thread
            Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
            Work->>Bus: emit ERROR_RAISED
        end
    end
```

Shell property reads are best-effort inside `AdbClient`; degraded enrichment can
still produce a successful outcome. Device listing failures fail the job.
