# Package 3 — Capabilities, Shell Results, and Location

## Finding 8. Device capability discovery

### Outcome

AROW knows which operations a live device supports and can explain degraded
readiness before an operation fails.

### Primary files

- new capability types/service in `src/core/adb/`
- `src/core/devices/phone.py`
- refresh/pair work and mock ADB
- device/readiness GUI blocks

### Implementation

1. Define a frozen `AdbDeviceCapabilities` with protocol facts (`shell_v2`,
   `stat_v2`) and product facts (`notification_post`, screenshot, helper package,
   mock-location readiness). Separate unknown from false.
2. Fetch ADB feature strings once per live transport and normalize to a
   `frozenset[str]`.
3. Probe product capabilities using bounded, read-only commands.
4. Cache by live connection/transport; invalidate on disconnect, rebind, server
   restart, or Android version change.
5. Return warnings for unsupported probes without failing basic device refresh.
6. Surface only operator-relevant readiness in the GUI.

### Tests and acceptance

- New, old, partial, malformed, and failed feature responses are covered.
- No capability probe runs against offline/unauthorized devices.
- Cached capabilities never survive a transport rebind incorrectly.

## Finding 9. Typed shell results

### Outcome

Shell operations expose remote exit code, stdout, stderr, and raw bytes without
relying on success substrings.

### Primary files

- `src/core/adb/command.py`
- new shell service/protocol code under `src/core/adb/`
- client, mock, parser, retry, and redaction tests

### Implementation

1. Add frozen `AdbShellResult` and separate decoding helpers.
2. Use shell-v2 framing where capabilities allow it; validate message IDs,
   lengths, and exit frames.
3. For legacy fallback, use a collision-resistant fixed wrapper/sentinel built
   entirely by trusted code. Do not concatenate untrusted command text.
4. Preserve list/tuple argv as the public default. If a fixed shell script is
   necessary, isolate and document it.
5. Map timeout/transport errors separately from non-zero remote exit status.
6. Apply command sensitivity metadata to stdout/stderr logs.

### Tests and acceptance

- Separate stdout/stderr, binary output, non-UTF-8 bytes, remote non-zero,
  missing exit frame, timeout, partial reads, and cancellation are covered.
- Existing simple getters may wrap the new result but retain their public
  behavior until callers are migrated.

## Finding 10. Complete mock-location service

### Outcome

AROW's central promise—starting, updating, verifying, and stopping mock
location—is implemented behind the model ADB boundary.

### Primary files

- replace stubs in `src/core/adb/client.py` and empty `SEND_LOCATION` descriptor
- new `src/core/adb/location_service.py` or equivalent
- simulation work/service/controller paths
- mock ADB and end-to-end core tests

### Product decisions required before implementation

- Which helper app/package and command/API receives coordinates?
- Which Android/API versions are supported?
- Does AROW enable location services automatically or ask permission?
- What constitutes verification: helper acknowledgement, `dumpsys location`, or
  observed coordinates?
- What cleanup is required on stop, disconnect, cancellation, and app exit?

### Implementation

1. Define typed inputs (`Location`, target, update mode) and outcomes
   (applied, verified, warnings).
2. Validate finite latitude/longitude ranges before command construction.
3. Add read-only preflight for location mode, helper version, mock-location
   authorization, device state, and required capabilities.
4. Implement start/update/stop as core work executed by `AsyncRunner`.
5. Redact all coordinate payloads from argv previews, stdout/stderr, history,
   exception messages, and support bundles by default.
6. Make start and stop idempotent. Ensure cancellation or device loss cannot
   leave model state reporting an active simulation incorrectly.
7. Verify application and emit typed success/failure on the main thread.

### Tests and acceptance

- Boundary coordinates, NaN/infinity, helper missing/outdated, permission
  missing, offline mid-update, timeout, retry, cancellation, stop, and repeated
  start are covered.
- GUI active state changes only after core apply succeeds.
- No coordinate or association code appears in captured logs.
- Real-device manual verification steps are documented separately.

