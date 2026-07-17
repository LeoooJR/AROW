# Render map async flow

Companion to [`render_map_work.py`](render_map_work.py). For shared runner and
dispatch conventions, see [`HOW_TO_async_jobs.md`](../../HOW_TO_async_jobs.md).

**Job:** `render_map` | **Pool:** process | **Coalesce key:**
`render_map:<simulation_id>`

```mermaid
sequenceDiagram
    autonumber
    participant View
    participant Controller as MapSubController
    participant Runner as AsyncRunner
    participant Entrypoint as ModelEntrypoint
    participant Work as RenderMapWork
    participant Disk as simulation map HTML
    participant Bus as Core signal bus

    View->>Controller: RenderMapRequested(simulation_id)
    alt simulation already has an existing map file
        Controller-->>View: forward cached map path<br/>no async submission
    else map must be rendered
        Controller->>Runner: submit render_map<br/>process, per-simulation latest wins
        alt simulation preflight fails
            Runner-->>Controller: no handle, skip submission
        else submission accepted
            Controller->>Controller: track handle by simulation ID
            Runner->>Entrypoint: static render_map(id, app_dir)<br/>in worker process
            Entrypoint->>Work: construct(picklable inputs) and run()
            Work->>Disk: Folium and dataset render to HTML
            alt render succeeds
                Work-->>Runner: RenderMapOutcome(id, html_path)
                Runner->>Entrypoint: apply_result(outcome) on main thread
                Entrypoint->>Work: apply_main_thread(entrypoint, outcome)
                alt simulation still exists
                    Work->>Entrypoint: set simulation.map_file
                    Work->>Bus: emit MAP_RENDERED
                    Bus-->>Controller: rendered payload
                    Controller-->>View: forward rendered map
                else simulation was deleted
                    Work->>Disk: delete orphan HTML best-effort
                end
                Runner->>Controller: Completed, then clear current handle
            else RenderMapError
                Work--xRunner: JobError origin render_map
                Runner->>Entrypoint: apply_failure(job_error) on main thread
                Entrypoint->>Work: apply_failure_main_thread(entrypoint, error)
                alt simulation still exists
                    Work->>Entrypoint: clear simulation.map_file
                    Work->>Bus: emit MAP_RENDER_FAILED
                    Bus-->>Controller: failure payload
                    Controller-->>View: forward render failure
                else simulation was deleted
                    Work->>Work: log warning only
                end
                Runner->>Controller: Failed, then clear current handle
            end
        end
    end
```

Deleting a simulation also cancels its tracked render handle. If a newer render
supersedes an older one, only the current handle is cleared when terminal signals
arrive.
