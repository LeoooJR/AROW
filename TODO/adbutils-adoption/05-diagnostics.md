# Package 5 — Diagnostics and Support

## Finding 15. Bounded logcat and sanitized support bundle

### Outcome

Users can export a disclosed, bounded support bundle containing useful evidence
without leaking credentials, stable identifiers, or coordinates by default.

### Primary files

- new diagnostics service under `src/core/adb/` and/or `src/core/`
- new async work and controller callback
- GUI export dialog/block
- logger redaction and bundle tests

### Implementation

1. Define bundle contents and privacy classification before coding:
   AROW logs, redacted ADB version/features, device state, helper-package logcat,
   recent redacted command history, optional screenshot.
2. Capture logcat with a fixed command, package/PID filtering, byte/time/line
   limits, cancellation, and explicit stream closure.
3. Re-resolve PIDs or use supported logcat filtering when the helper restarts.
4. Run every text artifact through a bundle redactor covering association codes,
   device IDs, hardware serials, stable keys, IPs when unnecessary, notification
   contents, and coordinates.
5. Show a manifest/preview and require explicit inclusion of screenshots or
   location-bearing data.
6. Write atomically to a user-selected `Path`; clean partial exports on failure.

### Tests and acceptance

- Test stream EOF, process restart, timeout, oversized input, cancellation,
  write failure, and every redaction category.
- Inspecting the ZIP/manifest reveals exactly the disclosed files.
- No ANSI coloring or terminal-only `pidcat` behavior enters the model layer.

## Finding 16. Optional screen recording

### Priority

Deferred. Implement only after a concrete support/product use case and consent
design are approved.

### Implementation constraints

1. Prefer a user-installed `scrcpy` executable discovered and version-checked at
   runtime; do not bundle an obsolete server JAR casually.
2. Start/stop through `AsyncRunner`, never raw daemon threads.
3. Display an unambiguous recording state and destination.
4. Use bounded graceful shutdown followed by kill only when required.
5. Clean AROW-owned remote files and preserve the primary error.
6. Treat video as highly sensitive; never add it to a support bundle implicitly.

### Acceptance criteria

- Consent, active indicator, stop, timeout, device disconnect, app shutdown,
  invalid output, disk-full, and cleanup paths are tested.
- No recording can continue after AROW reports it stopped.

