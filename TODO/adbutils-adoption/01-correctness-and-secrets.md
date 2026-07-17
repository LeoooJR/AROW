# Package 1 — Correctness, Actionable States, and Secrets

## Finding 1. Flexible `adb devices -l` parsing

### Outcome

AROW retains every valid device row with at least a connection ID and state,
regardless of optional tag count or order.

### Primary files

- `src/core/adb/command.py`
- `src/core/devices/phone.py`
- `src/core/adb/tests/test_adb_parser.py`
- `src/core/adb/adb_mock.py`

### Implementation

1. Add a frozen intermediate type such as `AdbDeviceListing` with
   `connection_id`, typed/raw `state`, and immutable `tags`.
2. Parse the first two whitespace tokens as ID/state. Parse remaining tokens
   with `partition(":")`; ignore malformed tag tokens but retain unknown keys.
3. Build `Phone` using named tags (`product`, `model`, `device`,
   `transport_id`) instead of positional unpacking.
4. Preserve rows for `unauthorized`, `offline`, `recovery`, `bootloader`, and
   future states even when no tags exist.
5. Keep shell enrichment restricted to state `device`.
6. Update mock fixtures to emit minimal, reordered, and unknown-tag rows.

### Tests

- Minimal two-token rows are returned.
- Tag order does not affect fields.
- Missing optional tags produce empty/`None` fields.
- Unknown tags do not fail parsing.
- Malformed one-token lines are skipped.
- Duplicate keys have a documented policy (recommended: last value wins).
- Values containing a colon retain text after the first colon.

### Acceptance criteria

- No valid actionable-state row disappears from the model.
- Existing enriched `device` rows retain their current displayed identity.
- Parser tests no longer encode a six-token requirement.

## Finding 2. Actionable device-state presentation

### Outcome

The device list distinguishes ready, unauthorized, offline, unsupported, and
absent states and gives the operator an appropriate next action.

### Primary files

- `src/core/devices/phone.py`
- `src/core/signals.py`
- `src/gui/blocks/device/`
- `src/gui/stylesheet.py`
- relevant block and integration tests

### Implementation

1. Define a core `DeviceConnectionState` enum or a normalization function that
   preserves unknown raw states.
2. Map state to UI semantic status and guidance:
   `device=ready`, `unauthorized=confirm debugging`, `offline=reconnect`,
   recovery/bootloader=`unsupported mode`, unknown=`attention`.
3. Keep copy and state rendering inside the device block; controllers only
   forward typed payloads.
4. Use existing color/status tokens and owner-local device settings.
5. Disable simulation selection for non-ready states without hiding the row.

### Tests and acceptance

- Each known state renders the expected badge, guidance, and enabled actions.
- Unknown states render safely.
- A transition from unauthorized/offline to device updates the same row.
- Light/dark screenshot tests remain legible.

## Finding 3. Disconnect versus forget workflow

### Outcome

The existing remove-device stub is replaced by explicit, asynchronous,
idempotent disconnect and forget operations.

### Primary files

- `src/core/adb/command.py`, `client.py`, `adb_mock.py`
- new work under `src/core/work/`
- `src/core/entrypoint.py`
- `src/controller/domains/adb_sub_controller.py`
- `src/controller/core_work_callbacks.py`
- GUI device block/signals and tests

### Implementation

1. Define product semantics before coding:
   **Disconnect** terminates the live ADB endpoint; **Forget** removes persisted
   simulation/device association. Do not silently combine them.
2. Add a typed `DISCONNECT` command and parser/result contract.
3. Implement `DisconnectDeviceWork` with preflight, bounded execution,
   main-thread apply, and generic failure handling.
4. Resolve the current endpoint from model state; treat "no such device" as an
   idempotent disconnected result.
5. Reconcile after command completion instead of mutating GUI state optimistically.
6. Implement forget only after confirming persistence semantics and add a
   confirmation UI if it deletes user data.

### Tests and acceptance

- Disconnect runs off the Qt main thread and coalesces repeated requests.
- Success, already-disconnected, timeout, cancellation, and wrong-device cases
  have tests.
- Disconnect never deletes saved simulation data.
- Forget never runs without the intended confirmation path.

## Finding 4. Pairing-code lifetime and disclosure

### Outcome

The six-digit association code exists only for command submission and is not
echoed into failure messages, retained payloads, activity logs, or UI copy.

### Primary files

- `src/core/work/authentificate_device_work.py`
- `src/core/signals.py`
- `src/controller/domains/adb_sub_controller.py`
- `src/gui/window.py`
- authentication card and logger tests

### Implementation

1. Remove `association_code` from failure exceptions and signal payloads.
2. Change GUI failure copy to identify the endpoint and reason only.
3. Clear OTP widgets immediately after submission, not only after success.
4. Ensure job/debug representations cannot print positional arguments containing
   the code; add redaction at the job boundary if necessary.
5. Retain existing ADB argv and structured-extra redaction as defense in depth.

### Tests and acceptance

- Search captured logs, errors, Qt signals, and visible failure text for a test
  code and assert it is absent.
- Pair retry can still reuse the code inside the active work object.
- The input is cleared on success, validation failure, ADB failure, cancellation,
  and controller shutdown.

