# Validate simulation marker location async flow

Companion to
[`validate_simulation_marker_location_work.py`](validate_simulation_marker_location_work.py).
For shared runner and dispatch conventions, see
[`HOW_TO_async_jobs.md`](../../HOW_TO_async_jobs.md).

**Job:** `validate_simulation_marker_location` | **Pool:** thread | **Coalesce
key:** `validate_simulation_marker_location:<simulation_id>`

```mermaid
sequenceDiagram
    autonumber
    participant Source as Map UI or restored simulation
    participant Controller as MapSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as ValidateSimulationMarkerLocationWork
    participant Geo as Railway and Milestone validators
    participant Bus as Core signal bus
    participant View

    Source->>Controller: location request or validation-requested core event
    Controller->>Runner: submit validation<br/>thread, per-simulation latest wins
    alt simulation preflight fails
        Runner-->>Controller: no handle, skip submission
    else submission accepted
        Runner->>Entrypoint: validate_simulation_marker_location(...)<br/>in worker thread
        Entrypoint->>Entrypoint: require simulation to exist
        Entrypoint->>Work: construct(location inputs) and run()
        Work->>Geo: validate railway, milestone, and point
        alt location is valid
            Geo-->>Work: validated line and milestone
            Work-->>Runner: outcome(validated payload)
            Runner->>Entrypoint: apply_result(outcome) on main thread
            Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
            Work->>Bus: emit SIMULATION_LOCATION_VALIDATED
            Bus-->>Controller: validated payload
            Controller-->>View: forward validated location
        else expected geo validation error
            Geo--xWork: RailwayValidationError or MilestoneValidationError
            Work-->>Runner: outcome(rejected payload)
            Note over Work,Runner: Rejection is a successful job result
            Runner->>Entrypoint: apply_result(outcome) on main thread
            Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
            Work->>Bus: emit SIMULATION_LOCATION_REJECTED
            Bus-->>Controller: rejected payload
            Controller-->>View: forward rejected location
        else unexpected exception
            Work--xRunner: exception in JobError<br/>origin validate_simulation_marker_location
            Runner->>Entrypoint: apply_failure(job_error) on main thread
            Entrypoint->>Work: apply_failure_main_thread(entrypoint, exception)
            Work->>Bus: emit ERROR_RAISED
        end
    end
```
