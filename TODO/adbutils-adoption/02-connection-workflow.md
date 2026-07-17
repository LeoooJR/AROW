# Package 2 — Connection Workflow and Responsiveness

## Finding 5. Pair → connect → wait → enrich state machine

### Outcome

Wireless setup reports meaningful phases and does not mark a phone ready until
ADB confirms state `device` and enrichment is attempted.

### Primary files

- `src/core/adb/command.py`, `client.py`, `exceptions.py`, `adb_mock.py`
- `src/core/work/authentificate_device_work.py`
- `src/core/signals.py`
- controller callbacks and authentication GUI

### Implementation

1. Add typed commands for `connect` and bounded `wait-for-device` or an
   equivalent polling protocol with a deadline.
2. Model phases: validating, pairing, connecting, waiting, enriching, ready.
3. Decide how the connect endpoint is obtained after pairing. Pairing port and
   connection port are not assumed identical; use mDNS discovery or explicit UI
   input according to platform-tools behavior verified in fixtures.
4. Emit progress through the existing async job, not ad-hoc core signals from a
   worker thread.
5. Check cancellation between phases and before retries.
6. Convert phase-specific failures into actionable, non-secret reasons.

### Tests and acceptance

- Cover already connected, pair-success/connect-required, delayed readiness,
  unauthorized, timeout, mDNS unavailable, protocol fault, and cancellation.
- No success signal occurs before state `device`.
- Retry policy does not repeat permanent authentication failures.

## Finding 6. Transport-aware command targeting

### Outcome

Commands prefer a live ADB transport ID when available and safely fall back to
the connection ID.

### Primary files

- `src/core/adb/client.py`
- `src/core/adb/command.py`
- `src/core/devices/phone.py`
- ADB execution/retry tests

### Implementation

1. Introduce an immutable `AdbTarget` value object with redacted diagnostic
   representation and mutually exclusive transport/serial selection.
2. Build argv with `-t <id>` when a valid current transport ID exists, otherwise
   `-s <connection-id>`.
3. Never use transport ID as persisted identity.
4. On device-not-found, permit one refresh/rebind before retrying only when the
   command's retry profile allows it.
5. Include targeting mode, not raw identifier, in logs/history.

### Tests and acceptance

- Verify exact raw argv and redacted log argv for both modes.
- Reject malformed transport IDs without command execution.
- Rebinding does not attach a command to a different stable phone.

## Finding 7. Event-driven device tracking

### Outcome

Device changes reach the UI promptly through a cancellable ADB tracking stream;
the 30-second timer becomes a recovery watchdog.

### Primary files

- new protocol/tracker module under `src/core/adb/`
- new long-lived work under `src/core/work/`
- `src/controller/runner.py` only if a missing lifecycle primitive is proven
- `src/controller/domains/adb_sub_controller.py`
- core/controller/mock tests

### Implementation

1. Implement only the required ADB server framing for `host:track-devices`:
   exact reads, `sendall`, explicit connect/read timeouts, `OKAY`/`FAIL` handling,
   maximum frame size, and context-managed closure.
2. Parse each snapshot through the same device-list parser used by refresh.
3. Diff snapshots into immutable `DeviceEvent` values, preserving state changes
   as remove/add or an explicit changed event.
4. Run the stream as an `AsyncRunner` thread job with a `CancelToken`; cancellation
   must close the socket to interrupt blocking reads.
5. Debounce event bursts into the existing coalesced refresh job. The tracker
   must not mutate `PhoneRepository` or Qt widgets.
6. Reconnect the stream with bounded backoff on transient daemon loss.
7. Keep a slower polling watchdog and manual refresh.

### Tests and acceptance

- Use a fake socket/server; no real device required.
- Cover partial frames, oversized/invalid length, `FAIL`, EOF, timeout,
  cancellation, reconnect, add, remove, and state change.
- Shutdown leaves no worker or socket alive.
- Normal changes appear substantially faster than the current 30-second poll.

