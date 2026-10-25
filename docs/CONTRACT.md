# Vision integration contract

## Session state across workers

`process_session_frame(...)` serializes processing for each `session_id`. If the session lock cannot be acquired within 500 ms, the frame is dropped and the result contains `dropped: true`, `signals: null`, and `reason: "session_lock_timeout"`. The store exposes a `frames_dropped_lock` counter.

Select the session store with `VISION_SESSION_STORE=memory|redis`. Memory is the default and keeps state only in one process; it evicts sessions after two hours without activity. Redis requires `VISION_REDIS_URL` and the optional `redis` Python package. Redis session state uses a two-hour idle TTL by default. Do not run multiple workers with the memory store unless requests for each session are reliably routed to the same worker.

Two deployment options are supported:

| Option | Use when | Trade-off |
|---|---|---|
| Redis session store | Multiple workers can receive frames for the same session | Shared state and distributed per-session locking; adds Redis operations and operations work |
| Sticky routing by `session_id` | Redis is unavailable and the load balancer can guarantee affinity | Fewer services, but worker restarts lose state and routing must remain stable |

For a multi-worker deployment without a proven sticky-routing guarantee, Redis is the safer default. The product owner should choose the deployment option based on the actual hosting environment.

`finish_session(session_id)` flushes open events and deletes the session state. Call it once when the exam session ends. `clear_session_state` remains a compatibility alias and also flushes before clearing.
