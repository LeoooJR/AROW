# Authenticate device async flow

Companion to [`authentificate_device_work.py`](authentificate_device_work.py).
For shared runner and dispatch conventions, see
[`HOW_TO_async_jobs.md`](../../../docs/HOW_TO_async_jobs.md).

**Job:** `authentification_workflow` | **Pool:** thread | **Coalesce key:**
`authentification`

```mermaid
sequenceDiagram
    autonumber
    participant View
    participant Controller as AdbSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as AuthenticateDeviceWork
    participant Bus as Core signal bus

    View->>Controller: AuthentificationConfirmed(ip, port, code)
    Controller->>Runner: submit authentification_workflow<br/>thread, latest wins
    Runner->>Entrypoint: authentificate_device(...) in worker thread
    Entrypoint->>Work: construct(current runtime references and inputs) and run()
    Work->>Work: preflight unpaired IP/port, server, client, host network, and mDNS
    Work->>Work: validate input, pair, and enrich phone
    opt ADB protocol fault
        Work->>Work: restart server and retry once
    end
    alt pairing succeeds
        Work-->>Runner: AuthentificateDeviceOutcome
        Runner->>Entrypoint: apply_result(outcome) on main thread
        Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
        Work->>Entrypoint: register paired phone
        Work->>Bus: emit DEVICE_AUTHENTIFICATION_SUCCEEDED
        Bus-->>Controller: success payload
        Controller-->>View: forward device success
    else validation, preflight, or pairing fails
        Work--xRunner: DeviceAuthentificationError in JobError
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit DEVICE_AUTHENTIFICATION_FAILED
        Bus-->>Controller: failure payload
        Controller-->>View: forward device failure
    else unexpected exception
        Work--xRunner: exception in JobError
        Runner->>Entrypoint: apply_failure(job_error) on main thread
        Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
        Work->>Bus: emit ERROR_RAISED
    end
```
