# Cross-Cutting Guardrails — Patterns Not to Copy

These are rejection criteria for every implementation package.

## Protocol and process safety

- No unbounded socket or subprocess wait.
- Use `sendall`, never assume `send` writes a complete frame.
- Use exact-read helpers for fixed-size frames; a single `recv(n)` is insufficient.
- Apply maximum lengths before allocating or decoding remote-controlled frames.
- Close sockets/processes deterministically on success, failure, and cancellation.
- A read-only connection or health method must not silently start ADB.

## Command safety

- Public command APIs accept typed/list arguments by default.
- Do not expose arbitrary shell strings to GUI/controller input.
- Fixed `sh -c` scripts must be constant, reviewed, and sensitivity-classified.
- Do not infer remote success solely from substrings such as `"Success"`.
- Preserve AROW's permanent/transient retry classification; never retry wrong
  pairing codes, permission failures, or invalid input automatically.

## Data and secret safety

- Pairing codes are ephemeral and absent from retained failures/signals.
- Device IDs, hardware serials, stable keys, IPs, coordinates, notification text,
  screenshots, and logs are sensitive according to context.
- No silent black screenshot, empty property, or swallowed exception may look
  like successful real data.
- Support artifacts require disclosure, redaction, size limits, and explicit
  handling of optional sensitive media.

## Lifecycle and architecture

- No raw `threading.Thread`; use `AsyncRunner` and cancellation tokens.
- No multiple-inheritance "god device" mirroring upstream extensions. Prefer
  focused services composed behind `AdbClient`/the core entrypoint.
- No mutable default collections.
- No runtime `pip install`, automatic dependency mutation, or implicit downloads.
- No destructive automatic uninstall/reinstall on signature/version errors.
- No caller-owned stream is closed unless the API explicitly transfers ownership.

## File/download safety

- Use `Path` for host files and approved remote-root policies for device files.
- Network downloads require explicit timeouts, maximum size, TLS, expected hash,
  and artifact/signature verification.
- Default transferred normal files to `0644`; executable permission is explicit.
- Temporary files are unique, AROW-owned, and cleaned without hiding primary errors.

