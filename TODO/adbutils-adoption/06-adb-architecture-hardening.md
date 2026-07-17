# Package 6 — ADB Architecture Hardening

## Finding 17. Shared ADB execution engine

### Outcome

Client and server facades share one implementation of argv construction,
timeouts, retries, history, redaction, and process result mapping.

### Implementation

1. Characterize existing client/server behavior with tests before extraction.
2. Introduce an internal `AdbExecutor`; keep `AdbClient` and `AdbServer` public
   methods as domain facades.
3. Pass immutable command, target, and extra-argument values to the executor.
4. Centralize process invocation, retry callbacks, sensitivity handling, result
   classification, and history append.
5. Preserve server-only and client-only exception contracts at facade boundaries.
6. Migrate one command family at a time; avoid a single rewrite commit.

### Acceptance criteria

- Existing ADB, parser, retry, history, and redaction tests remain green.
- Client/server no longer duplicate the subprocess attempt loop.
- Raw argv remains testable without being logged unsafely.

## Finding 18. Deeply immutable command specifications

### Outcome

`AdbCommand` cannot mutate after registration and directly declares execution
metadata needed by the executor.

### Implementation

1. Change `args` from `list[str]` to `tuple[str, ...]`; remove unsafe hashing if
   it is no longer necessary.
2. Inventory every construction, equality, registry, and mock use.
3. Consider adding typed metadata: parser key, sensitivity class, retry policy
   key, target requirement, timeout class, and remote-exit requirement.
4. Replace command-name string conditionals incrementally with metadata.

### Tests and acceptance

- Commands are hashable only if semantically required and cannot be mutated.
- Registry completeness and parser/sensitivity coverage tests fail when a new
  command omits required metadata.

## Finding 19. Structured bounded history

### Outcome

History cannot overwrite entries on timestamp collision and exposes safe,
useful timing/attempt data.

### Implementation

1. Introduce frozen `AdbHistoryEntry` with sequence, start time, duration,
   attempts, targeting mode, command identity, and result status.
2. Store entries in `deque(maxlen=...)`; do not use datetime as the key.
3. Keep raw sensitive output in memory only if required; exported/serialized
   views must be redacted.
4. Provide query helpers instead of mutable history setters/deleters.
5. Share history management through the executor.

### Tests and acceptance

- Same-time entries remain distinct and order-stable.
- Capacity eviction, retries, timeout duration, and sanitized export are covered.

## Finding 20. Enrichment values versus warnings

### Outcome

Missing device properties are distinguishable from failed reads without making
best-effort refresh brittle.

### Implementation

1. Define `DeviceEnrichment` containing typed values and immutable warnings.
2. Classify warning reason: unsupported, offline, timeout, permission, parse, or
   unexpected transport failure.
3. Batch property reads as today, but return warnings rather than collapsing all
   failures to empty strings.
4. Apply available values and preserve existing stable data when a transient
   refresh cannot reread it.
5. Surface only actionable warnings; log the rest with redacted context.

### Tests and acceptance

- Empty property success differs from command failure.
- A transient failed refresh does not erase prior manufacturer/model/serial data.
- Warning serialization contains no raw device ID or output.

## Finding 21. Real non-mutating ADB server health probe

### Outcome

Preflight reflects current daemon reachability rather than historical start/kill
commands while remaining non-mutating.

### Implementation

1. Add a short bounded local probe, preferably ADB `host:version` using the
   minimal protocol connection introduced for tracking.
2. Return typed health: running, stopped/refused, timeout, incompatible, unknown.
3. Never start the daemon from this probe.
4. Keep lifecycle history for diagnostics, not truth.
5. Update preflight and startup/shutdown tests for external daemon death/restart.

### Acceptance criteria

- Killing the daemon externally invalidates health promptly.
- Probe failure does not block explicit startup from attempting recovery.
- No read-only preflight mutates daemon state.

