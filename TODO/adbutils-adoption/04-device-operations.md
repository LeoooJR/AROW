# Package 4 — Device Operations

## Finding 11. Safe ADB Sync/file-transfer service

### Outcome

AROW can stream approved files to/from a device with progress, cancellation,
verification, and path policy.

### Primary files

- new modules under `src/core/adb/`
- transfer work under `src/core/work/`
- controller callbacks only when a GUI workflow requires them
- mock protocol and transfer tests

### Implementation

1. Confirm actual consumers first (helper APK, config, diagnostics); do not build
   a general file browser speculatively.
2. Implement Sync framing with `sendall`, exact reads, maximum path/frame sizes,
   timeouts, and explicit `FAIL` decoding.
3. Accept `Path`, bytes, or documented file-like objects. Close only streams
   opened by the service.
4. Default normal files to `0644`; require explicit executable mode.
5. Restrict remote destinations to approved roots such as `/data/local/tmp/`.
6. Report bytes through `ProgressEvent` and check cancellation between chunks.
7. Verify byte count and, when required, SHA-256 or signed artifact metadata.
8. Clean temporary remote files in `finally` without masking the primary error.

### Tests and acceptance

- Partial reads/writes, FAIL frames, missing files, directory targets, oversized
  inputs, path rejection, cancellation, checksum mismatch, and cleanup are tested.
- No unbounded `read_bytes()` is used for support artifacts without a size cap.

## Finding 12. Screenshot diagnostics

### Outcome

AROW can capture a real screenshot or return an explicit typed failure for
readiness and support workflows.

### Implementation

1. Add `screencap -p` as a binary shell command using `AdbShellResult`.
2. Decode with Pillow only if approved as a dependency; otherwise keep bytes and
   validate PNG signature/limits at the consumer boundary.
3. Add display enumeration/selection only after a multi-display use case exists.
4. Bound dimensions and encoded size before decoding.
5. Never convert failure into an apparently valid black screenshot.
6. Route capture and file writing through an async work item using `Path`.

### Tests and acceptance

- Valid PNG, corrupt/truncated image, oversized image, no display, offline,
  timeout, and cancellation are covered.
- Screenshots are opt-in for support bundles and their privacy impact is shown.

## Finding 13. Battery, screen, and device-readiness data

### Outcome

Existing battery/window parsers become a typed advisory readiness view rather
than unused test-only code.

### Implementation

1. Replace unstructured dictionaries with frozen `BatteryInfo` and
   `ScreenState` types; allow individual fields to be unknown.
2. Harden parsers against extra/missing/localized or vendor-specific lines.
3. Probe only ready devices and at a conservative cadence.
4. Define blocking versus advisory conditions explicitly. Low battery and screen
   off should normally warn, not block.
5. Add a compact GUI block using existing status components and design tokens.

### Tests and acceptance

- Partial/vendor output and invalid scalar fields do not crash refresh.
- Readiness probing cannot delay primary device-list first paint materially.
- Unknown data is displayed as unknown, not false or zero.

## Finding 14. Helper APK lifecycle

### Outcome

If AROW owns a device helper, it can inspect, install/update, launch, and verify
that exact package safely.

### Implementation

1. Record approved package name, signing certificate digest, supported versions,
   and bundled artifact SHA-256 in project configuration.
2. Inspect installed package/version/signature with typed parsers.
3. Transfer through the safe Sync service and install through a bounded typed
   shell result.
4. Verify size/hash before install and installed identity afterward.
5. Never automatically uninstall on signature or downgrade failure. Return an
   actionable decision to the GUI.
6. Clean only AROW-owned remote temporary paths.
7. Report progress through `AsyncRunner` and make cancellation semantics clear
   once package manager installation has begun.

### Tests and acceptance

- Missing, current, outdated, incompatible signature, downgrade, insufficient
  storage, install timeout, cancellation, verification failure, and cleanup paths
  are covered.
- No network APK URL is accepted without explicit product authorization,
  download limits, TLS, checksum, and signature verification.

